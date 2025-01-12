from flask import Flask, jsonify, request, abort, send_file
from flask_sqlalchemy import SQLAlchemy
from flask_swagger_ui import get_swaggerui_blueprint
from sqlalchemy.dialects.sqlite import JSON
from io import BytesIO
import google.generativeai as genai
import re
import fitz 
from flask_cors import CORS

genai.configure(api_key="AIzaSyCtdq_rEwBYQ9QM1lbU_dLMK7SlVhHttnM")
model = genai.GenerativeModel("gemini-1.5-flash")

app = Flask(__name__)
CORS(app)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///C:/Users/Xenko/Downloads/SQLite/test.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# Database Model
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)
    password = db.Column(db.String(100), unique=True, nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    pdf_files = db.relationship('PDFFile', backref='user', lazy=False)

    def to_dict(self):
        return {
                "id": self.id, 
                "name": self.name, 
                "password": self.password, 
                "email": self.email, 
                "pdfs": [file.to_dict() for file in self.pdf_files] 
                }

class DictEntry(db.Model):
    category = db.Column(db.String(50), primary_key=True)
    coef = db.Column(db.Float, nullable = False)
    
    def to_dict(self):
        return {
            "category": self.category,
            "coef": self.coef
        }


class PDFFile(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(255), nullable=False)
    file_content = db.Column(db.LargeBinary, nullable=False)  # Store file as BLOB
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    categories = db.Column(JSON, nullable=True)  # List of strings
    amounts = db.Column(JSON, nullable=True)  # List of floats
    emissions = db.Column(JSON, nullable=True)  # Another list of floats

    def to_dict(self):
        return {
            "id": self.id,
            "filename": self.filename,
            "user_id": self.user_id,
            "categories": self.categories,
            "amounts": self.amounts,
            "emissions": self.emissions
        }

SWAGGER_URL = '/swagger'
API_URL = '/static/swagger.yaml'  # Path to the swagger.yaml file
swaggerui_blueprint = get_swaggerui_blueprint(
    SWAGGER_URL,
    API_URL,
    config={'app_name': "Sample Flask API"}
)
app.register_blueprint(swaggerui_blueprint, url_prefix=SWAGGER_URL)

# Initialize database
with app.app_context():
    # db.drop_all()
    db.create_all()

# Routes
@app.route('/users', methods=['GET'])
def get_users():
    users = User.query.all()
    return jsonify([user.to_dict() for user in users])

@app.route('/DictEntries', methods=['GET'])
def get_entries():
    entries = DictEntry.query.all()
    return jsonify([entry.to_dict() for entry in entries])

@app.route('/users/<int:user_id>', methods=['GET'])
def get_user(user_id):
    # user = User.query.get(user_id)
    user = db.session.query(User).get(user_id)
    if not user:
        return abort(404, description="User not found")
    return jsonify(user.to_dict())

@app.route('/DictEntries', methods=['POST'])
def create_entry():
    if not request.json or not 'category' in request.json or not 'coef' in request.json:
        abort(400, description="Bad Request: Missing data")
    new_entry = DictEntry(
        category=request.json['category'],
        coef=request.json['coef']
    )
    return jsonify(new_entry.to_dict)

@app.route('/users', methods=['POST'])
def create_user():
    if not request.json or not 'name' in request.json or not 'email' in request.json or not 'password' in request.json:
        abort(400, description="Bad Request: Name and email are required")
    new_user = User(
        name=request.json['name'],
        password = request.json['password'],
        email=request.json['email']
    )
    db.session.add(new_user)
    db.session.commit()
    return jsonify(new_user.to_dict()), 201

@app.route('/users/<int:user_id>', methods=['PUT'])
def update_user(user_id):
    user = User.query.get(user_id)
    if not user:
        return abort(404, description="User not found")
    data = request.json
    user.name = data.get('name', user.name)
    user.email = data.get('email', user.email)
    user.password = data.get('password', user.password)
    db.session.commit()
    return jsonify(user.to_dict())

@app.route('/users/<int:user_id>', methods=['DELETE'])
def delete_user(user_id):
    user = User.query.get(user_id)
    if not user:
        return abort(404, description="User not found")
    db.session.delete(user)
    db.session.commit()
    return jsonify({"message": "User deleted successfully"})

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files or not request.form.get('user_id'):
        abort(400, description="File and user_id are required")
    
    file = request.files['file']
    user_id = request.form['user_id']
    listOfCategories = []
    entriesFromFile = GetCategoriesAndAmount(file)
    print(entriesFromFile)
    for key, _ in entriesFromFile.items():
        listOfCategories.append(key)
    print(listOfCategories)
    GetCoefs(listOfCategories)
    
    resultEntries = {}

    dbEntries = {entry.category: entry.coef for entry in DictEntry.query.all()}
    print(dbEntries)
    for key, value in entriesFromFile.items():
        if key in dbEntries:
            resultEntries[key] = value
    print(resultEntries) 
    
    category, amounts, coefs = [],[],[]
    for key, value in resultEntries.items():
        category.append(key)
        amounts.append(entriesFromFile[key])
        coefs.append(value*entriesFromFile[key])

    
    user = User.query.get(user_id)
    if not user:
        abort(404, description="User not found")
    
    new_file = PDFFile(
        filename=file.filename,
        file_content=file.read(),  # Read file content as binary
        user_id=user_id,
        categories = category,
        amounts = amounts,
        emissions = coefs
    )
    db.session.add(new_file)
    db.session.commit()
    return jsonify(new_file.to_dict()), 201

@app.route('/download/<int:file_id>', methods=['GET'])
def download_file(file_id):
    pdf_file = PDFFile.query.get(file_id)
    if not pdf_file:
        abort(404, description="File not found")
    
    return send_file(
        BytesIO(pdf_file.file_content),  # Create a file-like object from BLOB
        as_attachment=True,
        download_name=pdf_file.filename,
        mimetype='application/pdf'
    )

# Error handling
@app.errorhandler(404)
def not_found(error):
    return jsonify({"error": str(error)}), 404

@app.errorhandler(400)
def bad_request(error):
    return jsonify({"error": str(error)}), 400


def GetCategoriesAndAmount (pdf):

    dict = {}

    pdf_document = fitz.open(stream=pdf.read(), filetype="pdf")
    text = ""
    for page_num in range(pdf_document.page_count):
        page=pdf_document.load_page(page_num)
        text += page.get_text()
    
    prompt = (
        f"Below is a text of an PDF file with a table:%PDF_file start% {text}. %PDF_file end%"
        "You should find the name of the products in the table"
        "You should find the amount of produced products in the table"
        "Return the answer in the format product:amount, product2:amount. "
        "The anwser should be only product:amount, product:amount, as example steel:5, amount must be in 1 kg or in one unit and nothing else, the anwser list must be written between /"
        )
    response = model.generate_content(prompt)
    candidate = response.candidates[0]
    response_text = str(candidate.content)
    match = re.search(r"/([^/]*)/", response_text)
    if match:
            # Получаем строку между слэшами, например 
            content = match.group(1).strip()
            
            # Разбиваем по запятым
            pairs = content.split(",")
            
            for pair in pairs:
                pair = pair.strip()  # убираем пробелы по краям
                # Разделяем по двоеточию 
                obj, val_str = pair.split(":")
                
                dict[obj.strip()] = float(re.sub(r'[^0-9]','',val_str.strip()))
    return dict
    
    


def GetCoefs (check):
    Coefs = []
    
    get_coef = []
    #"car", "iron", "plastic", "rice", "paper", "bread"
    

    check_string = ", ".join(check)
    dict = {entry.category: entry.coef for entry in DictEntry.query.all()}

    for key in check:
        if key in dict:
            pass
        else:
            get_coef.append(key)
    print(get_coef)  
    get_coef_str = ", ".join(get_coef)

    if not get_coef:
        for item in check:
                Coefs.append(dict[item])
    else:
    # Формируем промпт
        prompt = (
        f"Below is a list of materials or categories: {get_coef_str}. "
        "For each item, please provide the average aproximate average CO2 emission coefficient for producing one unit or "
        "one kilogram of that material/object. "
        "Return the answer in the format material:coefficient, material2:coefficient. "
        "The anwser should be only material:coefficient, material:coefficient, as example weed:0.5, coeficent must be in 1 kg or ine unit and nothing else, the anwser list must be written between /"
        "You must include some coefficent even if you do not know the answer, you cannot answer that you cannot provide a coefficent"
        "Do not write anything other that material:coefficent, nothing except this"
        )
        # Инициализируем модель
        # Отправляем промпт модели
        response = model.generate_content(prompt)
        candidate = response.candidates[0]
        response_text = str(candidate.content)
        print(response_text)
        match = response.text.split("\n")
        print(match)
        if match:
            # Получаем строку между слэшами, например 
            content = match[0].strip()
            
            # Разбиваем по запятым
            pairs = content.split(",")
            
            for pair in pairs:
                pair = pair.strip()  # убираем пробелы по краям
                # Разделяем по двоеточию 
                obj, val_str = pair.split(":")
                
                dict[obj.strip()] = float(re.sub(r'[^0-9]','',val_str.strip()))
                
            for item in check:
                Coefs.append(dict[item])
            i = 0
            for key in get_coef:
                new_entry = DictEntry(category=key,coef=Coefs[i])
                print("added")
                db.session.add(new_entry)
                i = i+1
    db.session.commit()
     

if __name__ == '__main__':
    app.run(debug=True)
    
