import os
import json
from flask import Flask, request, jsonify
from flask_cors import CORS
import firebase_admin
from firebase_admin import credentials, firestore
import google.generativeai as genai

# --- CONFIGURAÇÃO INICIAL ---
app = Flask(__name__)
CORS(app)

# Carrega as credenciais do Firebase a partir de uma variável de ambiente
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
        return jsonify({"error": "O servidor não está configurado corretamente."}), 500
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
        Gere um quiz com {count} questões sobre "{topic}".
        Nível: Ensino médio, dificuldade 6 a 9 (de 10).
        As questões devem ser como atividades de aula (cálculo em exatas, análise em humanas).
        REGRAS: Posição da resposta correta aleatória, tamanho das opções variado, perguntas originais.
        IMPORTANTE: EXCLUA perguntas semanticamente similares a estas:
        {prompt_exclusoes if perguntas_ja_feitas else "Nenhuma."}
        """

        model = genai.GenerativeModel('gemini-1.5-flash')
        
        # Correção: Definir o schema e pedir explicitamente um JSON
        schema = {
            "type": "object", "properties": { "quiz": { "type": "array", "items": { "type": "object", "properties": { "pergunta": {"type": "string"}, "opcoes": {"type": "array", "items": {"type": "string"}}, "respostaCorreta": {"type": "string"}, "explicacao": {"type": "string"} }, "required": ["pergunta", "opcoes", "respostaCorreta", "explicacao"] } } }, "required": ["quiz"]
        }
        
        response = model.generate_content(
            prompt,
            generation_config=genai.types.GenerationConfig(
                response_mime_type="application/json",
                response_schema=schema
            )
        )
        
        novo_quiz = json.loads(response.text)

        for questao in novo_quiz.get("quiz", []):
            questions_ref.add(questao)

        return jsonify(novo_quiz)
    except Exception as e:
        print(f"Ocorreu um erro em /generate-quiz: {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/analyze-performance", methods=["POST"])
def analyze_performance():
    if not GEMINI_API_KEY:
        return jsonify({"error": "O servidor não está configurado corretamente."}), 500
    try:
        data = request.get_json()
        topic = data.get("topic")
        results = data.get("results")

        resultsText = "\n\n".join(
            f"Questão: \"{res['pergunta']}\"\nResposta dada: \"{res['respostaDada']}\"\nResultado: {'Acerto' if res['acertou'] else 'Erro'}"
            for res in results
        )

        prompt = f"""
        A aluna Ysraelly completou um quiz sobre "{topic}". Analise os seus ERROS.
        Para cada erro, identifique a causa provável (ex: confusão conceitual, erro de cálculo, etc.) e dê uma recomendação de estudo.
        No final, forneça um diagnóstico geral e encorajador.

        Resultados do Quiz:
        {resultsText}
        """
        
        model = genai.GenerativeModel('gemini-1.5-flash')

        # Correção: Definir o schema e pedir explicitamente um JSON
        schema = {
            "type": "object", "properties": { "analise": { "type": "object", "properties": { "diagnosticoGeral": {"type": "string"}, "analiseDosErros": { "type": "array", "items": { "type": "object", "properties": { "pergunta": {"type": "string"}, "causaProvavel": {"type": "string"}, "recomendacao": {"type": "string"} }, "required": ["pergunta", "causaProvavel", "recomendacao"] } } }, "required": ["diagnosticoGeral", "analiseDosErros"] } }, "required": ["analise"]
        }

        response = model.generate_content(
            prompt,
            generation_config=genai.types.GenerationConfig(
                response_mime_type="application/json",
                response_schema=schema
            )
        )
        
        analysis_json = json.loads(response.text)

        return jsonify(analysis_json)
    except Exception as e:
        print(f"Ocorreu um erro em /analyze-performance: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/")
def index():
    return "O cérebro da Veruska está online e pronto para criar quizzes!"