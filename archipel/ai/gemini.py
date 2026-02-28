"""
ai/gemini.py
Module d'intégration Gemini API pour Archipel.
"""
import os
import requests
from dotenv import load_dotenv

load_dotenv()

def query_gemini(conversation_context, user_query, api_key=None):
    """
    Envoie une requête à Gemini avec le contexte et la question utilisateur.
    Retourne la réponse IA ou une erreur si offline.
    """
    api_key = api_key or os.getenv("GEMINI_API_KEY")
    if not api_key:
        return {"error": "API Gemini non configurée."}
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent?key={api_key}"
    payload = {
        "contents": [
            {
                "role": "user",
                "parts": [{"text": build_prompt(conversation_context, user_query)}]
            }
        ]
    }
    try:
        response = requests.post(url, json=payload, headers={"Content-Type": "application/json"}, timeout=10)
        response.raise_for_status()
        return response.json()
    except Exception as exc:
        return {"error": f"Gemini inaccessible: {exc}"}

def build_prompt(conversation_context, user_query):
    """
    Construit le prompt à envoyer à Gemini à partir du contexte et de la question.
    """
    context_text = "\n".join(conversation_context)
    return f"Contexte:\n{context_text}\nQuestion:\n{user_query}"

if __name__ == "__main__":
    # Exemple de test manuel
    context = [
        "User: Bonjour, peux-tu m'expliquer le protocole Archipel?",
        "Bot: Bien sûr! Archipel est un protocole P2P..."
    ]
    user_query = "Quels sont les avantages de la cryptographie utilisée?"
    api_key = os.getenv("GEMINI_API_KEY") or "VOTRE_CLE_API_GEMINI"
    print("Envoi de la requête à Gemini...")
    result = query_gemini(context, user_query, api_key=api_key)
    print("Réponse Gemini:")
    print(result)
