import os

from cs50 import SQL
from flask import Flask, flash, jsonify, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash, safe_str_cmp



from helpers import apology, login_required, lookup, usd, user_total, register_operation

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Ensure responses aren't cached
@app.after_request
def after_request(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

# Make sure API key is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""

    user = session["user_id"]


    #Access database for datas

    stocks = db.execute("SELECT * from stocks JOIN users ON stocks.id = users.id_user WHERE id_user = :useid",useid = user)
    cash = db.execute("SELECT cash from users WHERE id_user = :id_number", id_number = user)

    prices = [] # list of owned stocks prices
    totals = [] # list of owned stocks totals
    u_cash = cash[0]["cash"] # user cash
    sum_totals = 0 # sum total stocks money

    # loop filling prices and totals lists and total money
    if (len(stocks) > 0):
        for i in range(len(stocks)):
            stock = lookup(stocks[i]["symbol"])
            price = stock["price"]
            prices.append(price)

            share_qty = stocks[i]["shares"]

            totals.append(price * share_qty)
            sum_totals += price * share_qty

    else:
        totals.append(u_cash) # if there is no stocks totals = user cash

    total = sum_totals + u_cash # total user money

    # render index page passing all user infos to display

    return render_template("index.html", user_stocks = stocks, user_cash = u_cash, stocks_prices = prices, stocks_totals = totals, user_total = total)



@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""


    # User reached route via GET (as by clicking a link or via redirect)
    if request.method == "GET":
        return render_template("buy.html")

    # User reached route via POST
    else:

        # Ensure username was submitted
        if not request.form.get("symbol"):
            return apology("must provide a valid symbol", 403)

        # Ensure password was submitted
        elif not request.form.get("shares"):
            return apology("must provide a valid number of shares", 403)

        # Ensure symbol exists
        elif (lookup(request.form.get("symbol")) == None):
            return apology("must provide a valid symbol", 403)

        # Ensure shares is a positive number and higher then 0
        elif (int(request.form.get("shares")) <= 0):
            return apology("must provide a valid number of shares", 403)


        symbol = lookup(request.form.get("symbol")) # Get symbol infos
        shares = request.form.get("shares") # Get amount of shares entered

        user = session["user_id"] # Get user id

        _cash = db.execute("SELECT cash FROM users WHERE id_user = :user_id", user_id = user)

        cash = _cash[0]["cash"] # Get user cash
        total = symbol["price"] * float(shares) # Calculate total value of shares to buy

        # if user has cash to buy
        if (total < cash):

            symb = db.execute("SELECT symbol FROM stocks WHERE id = :useid AND symbol = :symbol", useid = user, symbol = symbol["symbol"])

            # if user have any stock
            if len(symb) == 0:
                db.execute("INSERT INTO stocks VALUES (:id_number, :symbol, :name, :shares)",
                symbol = symbol["symbol"],
                shares = shares,
                id_number = user,
                name = symbol["name"])

            # if user dont have that stock yet
            elif symbol["symbol"] not in symb[0]["symbol"]:
                db.execute("INSERT INTO stocks VALUES (:id_number, :symbol, :name, :shares)",
                symbol = symbol["symbol"],
                shares = shares,
                id_number = user,
                name = symbol["name"])

            # if user already have that stock
            else:
                _user_shares = db.execute("SELECT shares from stocks WHERE id = :useid AND symbol = :symbol", useid = user, symbol = symbol["symbol"])
                user_shares = _user_shares[0]["shares"] + int(shares)
                db.execute("UPDATE stocks SET shares = :user_shares WHERE id = :useid AND symbol = :symbol", user_shares = user_shares, useid = user, symbol = symbol["symbol"])

            # update user cash
            update_cash = cash - total
            db.execute("UPDATE users SET cash = :new_cash WHERE id_user = :useid", new_cash = update_cash, useid = user)

            register_operation(user, symbol["symbol"], shares, symbol["price"], None, db) # register the operation

            # Redirect user to home page
            return redirect("/")

        # if user dont have enough money
        else:
            return apology("Sorry, you can't afford it")


@app.route("/history")
@login_required
def history():

    """Show history of transactions"""
    # show a table of all user transactions

    user = session["user_id"] # Get user id
    _history = db.execute("SELECT * from history WHERE id = :userid AND shares > 0", userid = user)

    # render history template
    return render_template("history.html", history = _history)

@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = :username",
                          username=request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id_user"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Quote a stock"""

    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("symbol"):
            return apology("must provide a valid Symbol", 403)


        # Query database for symbol
        symbol = lookup(request.form.get("symbol"))

        if (symbol == None):
            return apology("must provide a valid symbol")

        # Redirect user to home page
        return render_template("quoted.html", symbol = symbol)

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("quote.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""

    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = :username",
                          username=request.form.get("username"))

        # Ensure username exists and password is correct
        if (len(rows) != 0):
            return apology("Sorry, username already exists", 403)

        # Ensure password matches to confirm_password
        if (safe_str_cmp(request.form.get("password"),request.form.get("confirm_password")) == False):
            return apology("Sorry, passwords does not match")

        # store username and hash password to the database
        else:
            db.execute("INSERT INTO users (username, hash) VALUES (:username,:hash_pass)",
            username = request.form.get("username"),
            hash_pass = generate_password_hash(request.form.get("password")))


        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""

    user = session["user_id"] #Get user id

    # Get user data
    stocks = db.execute("SELECT * from stocks JOIN users ON stocks.id = users.id_user WHERE id_user = :useid",useid = user)
    _cash = db.execute("SELECT cash from users WHERE id_user = :id_number", id_number = user)

    # if reached route via GET, display form to sell
    if request.method == "GET":

        # if user has stocks
        if len(stocks) > 0:
            stocks_symbols = []
            for i in range(len(stocks)):
                stocks_symbols.append(stocks[i]["symbol"])

            return render_template("sell.html", stocks_symbols = stocks_symbols)

        # if user dont have stocks
        else:
            return apology("You have no shares to sell")

    # if reached route via POST, update database
    else:

        # Ensure symbol was submitted
        if not request.form.get("symbol"):
            return apology("must provide a valid symbol", 403)

        # Ensure shares was submitted
        elif not request.form.get("shares"):
            return apology("must provide a valid number of shares", 403)

        # Ensure symbol exists
        elif (lookup(request.form.get("symbol")) == None):
            return apology("must provide a valid symbol", 403)


        # Ensure shares is a positive number and higher then 0
        elif (int(request.form.get("shares")) <= 0):
            return apology("must provide a valid number of shares", 403)


        symbol = request.form.get("symbol") # get symbol entered
        shares = request.form.get("shares") # get number of shares entered

        # get user shares
        _shares = db.execute("SELECT shares from stocks WHERE symbol = :sym AND id = :useid", sym = symbol, useid = user)
        user_shares = _shares[0]["shares"]

        left_shares = user_shares - int(shares) # calculate shares left after selling

        stock = lookup(symbol) # get stock infos
        cash = _cash[0]["cash"] # get user cash
        value = float(shares) * stock["price"] # calculate value of the transaction

        # if user sell all his shares
        if (left_shares == 0):
            # delete the stock row in the database
            db.execute("DELETE from stocks WHERE symbol = :sym AND id = :useid" , sym = symbol, useid = user)

            cash_update = float(cash + value) #update cash
            db.execute("UPDATE users SET cash = :new_cash WHERE id_user = :user", new_cash = cash_update, user = user)
            register_operation(user, symbol, -shares, stock["price"], None, db) # register transaction
            return (redirect("/"))

        # if user dont sell all his shares
        elif (shares <= user_shares):
            # update user shares
            db.execute("UPDATE stocks SET shares = :shares WHERE id = :user AND symbol = :sym", shares = left_shares, user = user, sym = symbol)

            cash_update = float(cash + value) # update cash
            db.execute("UPDATE users SET cash = :new_cash WHERE id_user = :user", new_cash = cash_update, user = user)


            register_operation(user, symbol, -shares, stock["price"], None, db) #register transaction
            return (redirect("/"))

        # if user tries to sell more shares than he has
        else:
             return apology("You dont have that amount of shares")

@app.route("/add_cash", methods=["GET", "POST"])
@login_required
def add_cash():
    """Allows user to add cash"""

    user = session["user_id"] # Get user id
    # if reached route via get, display user transactions history
    if request.method == "GET":
        _cash = db.execute("SELECT * FROM history WHERE id = :useid AND cash_added > 0", useid = user)
        return render_template("add_cash.html", cash = _cash)

    # if reached route via post, update database
    else:
        cash_added = float(request.form.get("money")) # get amount added

        _cash = db.execute("SELECT cash from users WHERE id_user = :useid", useid = user) # get user cash
        user_cash = float(_cash[0]["cash"])

        new_cash = user_cash + cash_added # calculate new user cash
        db.execute("UPDATE users SET cash = :new_cash WHERE id_user = :useid", new_cash = new_cash, useid = user) # update user cash

        register_operation(user, None, None, None, cash_added, db) # register operation
        return redirect("/")



def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)


# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)
