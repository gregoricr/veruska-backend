import os
import json
from flask import Flask, request, jsonify
import firebase_admin
from firebase_admin import credentials, firestore
import google.generativeai as genai

# --- CONFIGURAÇÃO INICIAL ---
app = Flask(__name__)

# Carrega as credenciais do Firebase a partir de uma variável de ambiente
# Isto é mais seguro para produção!
cred_json_str = os.environ.get("GOOGLE_CREDENTIALS_JSON")
if cred_json_str:
    cred_info = json.loads(cred_json_str)
    cred = credentials.Certificate(cred_info)
    firebase_admin.initialize_app(cred)
    db = firestore.client()
else:
    print("AVISO: A variável de ambiente GOOGLE_CREDENTIALS_JSON não foi encontrada.")
    db = None

# Carrega a chave da API do Gemini a partir de uma variável de ambiente
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
else:
    print("AVISO: A variável de ambiente GEMINI_API_KEY não foi encontrada.")

# --- FIM DA CONFIGURAÇÃO ---

@app.route("/generate-quiz", methods=["POST"])
def generate_quiz():
    if not db or not GEMINI_API_KEY:
        return jsonify({"error": "O servidor não está configurado corretamente. Verifique as variáveis de ambiente."}), 500
    # ... (o resto da função generate_quiz continua exatamente igual)
    try:
        data = request.get_json()
        topic = data.get("topic")
        count = data.get("count")

        if not topic or not count:
            return jsonify({"error": "Tópico ou número de questões em falta."}), 400

        questions_ref = db.collection("quizzes").document(topic).collection("questions")
        docs = questions_ref.stream()

        perguntas_ja_feitas = [doc.to_dict().get("pergunta") for doc in docs]

        prompt_exclusoes = "\n".join(f"- {p}" for p in perguntas_ja_feitas)

        prompt = f"""
        Gere um quiz interativo com {count} questões sobre o tópico "{topic}".
        O público-alvo é uma aluna de ensino médio inteligente. A dificuldade das questões deve ser cuidadosamente calibrada: numa escala de 0 (muito fácil) a 10 (muito difícil), as questões devem variar entre os níveis 6 e 9.
        As questões devem simular uma atividade de aula real para o ensino médio (exigindo cálculo em exatas, análise em humanas, etc.).
        REGRAS OBRIGATÓRIAS DE QUALIDADE:
        1. A posição da resposta correta (A, B, C, D) deve ser totalmente aleatória e distribuída.
        2. O comprimento das opções de resposta deve ser variado. A resposta correta NÃO deve ser consistentemente a mais longa ou a mais curta.
        3. Formule perguntas originais e criativas.
        IMPORTANTE: EXCLUA OBRIGATORIAMENTE da sua resposta qualquer pergunta que seja semanticamente similar às seguintes questões já feitas:
        {prompt_exclusoes if perguntas_ja_feitas else "Nenhuma."}
        """

        model = genai.GenerativeModel('gemini-1.5-flash')
        response = model.generate_content(prompt)

        quiz_text = response.text.replace("```json", "").replace("```", "").strip()
        novo_quiz = json.loads(quiz_text)

        for questao in novo_quiz.get("quiz", []):
            questions_ref.add(questao)

        return jsonify(novo_quiz)

    except Exception as e:
        print(f"Ocorreu um erro: {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/")
def index():
    return "O cérebro da Veruska está online e pronto para criar quizzes!"

# O if __name__ == "__main__" não é necessário para produção no Render,
# mas podemos mantê-lo para testes locais.
