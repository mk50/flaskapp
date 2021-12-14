from enum import unique
from flask import Flask, request, render_template, redirect, url_for
from flask.helpers import flash
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt, check_password_hash, generate_password_hash
from flask_login import LoginManager, login_required, current_user, login_user, logout_user, UserMixin
from sqlalchemy import func
from datetime import datetime
from flask_migrate import Migrate
from wtforms import Form, BooleanField, StringField, PasswordField, validators


# def render(temp_name, context):
#     return render_template(temp_name, **context)


# app = Flask(__name__, template_folder='temp')
app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///todos_db"
app.config["SECRET_KEY"] = "supersecret"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
# app.config["SQLALCHEMY_DATABASE_URI"] = "[db-adapter]://[username]:[password]@[host]:[port]/[db-name]"
# app.config["SQLALCHEMY_DATABASE_URI"] = "postgres://root:123@localhost:5432/todos_db"
db = SQLAlchemy(app)
bcrypt = Bcrypt(app)
login_manager = LoginManager(app)
# db = SQLAlchemy()
# db.init_app(app)
migrate = Migrate(app, db)

# @migrate.configure
# def configure_alembic(config):
#     # modify config object
#     return config


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(user_id)

class RegistrationForm(Form):
    username = StringField('Username', [validators.Length(min=4, max=25)])
    email = StringField('Email Address', [validators.Length(min=6, max=35)])
    password = PasswordField('New Password', [
        validators.DataRequired(),
        validators.EqualTo('confirm', message='Passwords must match')
    ])
    confirm = PasswordField('Repeat Password')
    accept_tos = BooleanField('I accept the TOS', [validators.DataRequired()])
    
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(50), unique=True, nullable=False)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(40), nullable=False)
    todos = db.relationship('Todo', lazy=True, backref='user')
    # lazy='select'|True
    # lazy='join'|False
    # lazy='subquery'
    # lazy='dynamic'

    def check_password(self, password):
        return check_password_hash(self.password, password)

    def set_password(self, password):
        self.password = generate_password_hash(password)

    # def get_id(self):
    #     return self.id

    # @property
    # def is_authenticated(self):
    #     return True

    # @property
    # def is_anonymous(self):
    #     return False

    # @property
    # def is_active(self):
    #     return True


class Todo(db.Model):
    # __tablename__ = 'todos'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(50), unique=True, nullable=False)
    description = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False,
                           default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey(
        'user.id'), nullable=True)
    # user = db.relationship('User', lazy=True, backref='todos')
    is_done = db.Column(db.Boolean, default=False, nullable=True)

    def __str__(self):
        return f"<Todo:{self.id} ({self.title})>"
        # return "<Todo:{%s} ({%s})".format(self.id, self.title)

    def __repr__(self):
        return f"<Todo:{self.id} ({self.title})>"

    @classmethod
    def search(cls, user_id, query):
        # Full-Text index, Accuracy vs Recall, Drawbacks for regex
        # return Todo.query.filter(Todo.title.ilike(f"%{query}%") | Todo.description.ilike(f"%{query}%"))
        return Todo.query.filter(Todo.user_id == user_id).filter(
            func.lower(Todo.title).contains(query.lower()) |
            func.lower(Todo.description).contains(query.lower())
        ).all()


@app.route("/")
@app.route("/home")
@login_required
def index():
    # context = { "todos": todos }
    todos = current_user.todos  # N+1 problem
    undones = []
    for todo in todos:
        if todo.is_done == False:
            undones.append(todo)
    return render_template("index.html", todos=undones)



@app.route("/todos_done")
@login_required
def todos_done():
    todos = current_user.todos
    dones = []
    for todo in todos:
        if todo.is_done == True:
            dones.append(todo)
    # return render_template("index.html", todos=dones)
    return render_template("todos_done.html", todos=dones)
    
        
    
    
@app.route("/search")
@login_required
def search():
    q = request.args.get('q')
    if not q:
        return "Invalid search query"
    # todos = Todo.query.filter_by(title=q.lower(), description=q.lower())
    # todos = Todo.query.filter(
    #     (Todo.title == q.lower()) | (Todo.description == q.lower())
    # ).all()
    # todos = Todo.query.filter(
    #     (Todo.title.contains(q.lower())) | (
    #         Todo.description.contains(q.lower()))
    # ).all()
    todos = Todo.search(current_user.id, q)
    # filtered = list(filter(lambda todo: q.lower() in todo['title'].lower(
    # ) or q.lower() in todo['description'].lower(), todos))
    return render_template("index.html", todos=todos)


@app.route("/todo", methods=["GET", "POST"])
@login_required
def create_todo():
    if request.method == "POST":
        todo = Todo(title=request.form.get("title"),
                    description=request.form.get("description"),
                    # is_done=request.form.get("done"),
                    user_id=current_user.id)
        db.session.add(todo)
        db.session.commit()
        return redirect(url_for('index'))
    return render_template("todo_form.html")


@app.route("/todo/<int:id>", methods=["GET"])
@login_required
def get_todo(id):
    todo = Todo.query.filter_by(user_id=current_user.id, id=id).first()
    if not todo:
        return render_template("not_found.html")
    return render_template("todo.html", todo=todo)


@app.route("/todo/<int:id>/done")
@login_required
def done_todo(id):
    todo = Todo.query.get(id)
    if not todo:
        return render_template("not_found.html")
    if todo.is_done == True:
        return 'You Cant Update Finished Todo'
    todo.is_done = True
    db.session.add(todo)
    db.session.commit()
    return redirect(url_for("todos_done", id=id))
   

@app.route("/todo/<int:id>/edit", methods=["GET", "POST"])
@login_required
def edit_todo(id):
    todo = Todo.query.get(id)
    if not todo:
        return render_template("not_found.html")
    if todo.is_done == True:
        return 'You Cant Update Finished Todo'
    if request.method == 'POST':
        todo.title = request.form.get("title")
        todo.description = request.form.get("description")
        print(request.form.get("done"))
        todo.is_done = request.form.get("done")
        db.session.add(todo)
        db.session.commit()
        return redirect(url_for("get_todo", id=id))
    return render_template("todo_form.html", todo=todo)


@app.route('/todo/<int:id>/delete', methods=['GET','POST'])
def delete_todo(id):
    todo = Todo.query.get(id)
    if not todo:
        return render_template("not_found.html")
    if request.method == 'POST':
        if todo:
            db.session.delete(todo)
            db.session.commit()
            return redirect(url_for('index'))
    return render_template('delete.html', todo=todo)



@app.route('/login', methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        user = User.query.filter_by(email=request.form.get("email")).first()
        # print(user)
        if not user or not user.check_password(request.form.get("password")):
            error = 'This User Dosent Exist, Please Register First!'
            return render_template("login.html", error = error)
               
        login_user(user)
        user.todos
        return redirect(url_for("index"))
    return render_template("login.html")


@app.route('/register', methods=["GET", "POST"])
def register(): 
    form = RegistrationForm(request.form)
    if request.method == 'POST' and form.validate():
        user = User(username=form.username.data, email=form.email.data)
        user.set_password(form.password.data)
        db.session.add(user)
        flash('Thanks for registering')
        try:
            db.session.commit()
        except Exception as e:
            print(e.args)
            print("User already exists")
            return redirect(url_for('register'))
        login_user(user)
        return redirect(url_for('index'))
    return render_template('register.html', form=form)

    # if request.method == "POST":
    #     if request.form.get('password') != request.form.get('confirm_password'):
    #         return redirect(url_for('register'))
    #     user = User(
    #         email=request.form.get('email'),
    #         username=request.form.get('username'),
    #     )
    #     user.set_password(request.form.get('password'))
    #     db.session.add(user)
    #     try:
    #         db.session.commit()
    #     except Exception as e:
    #         print(e.args)
    #         print("User already exists")
    #         return redirect(url_for('register'))
    #     login_user(user)
    #     return redirect(url_for('index'))
    # return render_template("register.html")


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))


if __name__ == '__main__':
    app.run("127.0.0.1", "9000", debug=True)


# Flask_WTF
