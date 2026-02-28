from flask import Flask, render_template_string, request, jsonify
import subprocess
import threading
import time

app = Flask(__name__)

GEMINI_API_KEY = "AIzaSyA3eQ4R1wHPoOnsnkqFeUIvs9OPfmpS3Dw"

TEMPLATE = '''
<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <title>Archipel - Démo Sprints & IA Gemini</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 40px; background: #f8fafc; }
        .card { background: #fff; border-radius: 12px; box-shadow: 0 2px 8px #0001; margin-bottom: 30px; padding: 30px; }
        button, input[type=text] { margin: 10px; padding: 10px 20px; font-size: 16px; border-radius: 6px; border: 1px solid #ddd; }
        button { background: #2563eb; color: #fff; cursor: pointer; }
        button:hover { background: #1d4ed8; }
        #result, #ia-result, #sprint1-result, #sprint2-result, #sprint3-result { margin-top: 30px; white-space: pre-wrap; background: #f4f4f4; padding: 20px; border-radius: 8px; }
        #ia-box { margin-top: 40px; }
        h1, h2 { color: #2563eb; }
        .loader { display: none; margin: 20px auto; border: 6px solid #f3f3f3; border-top: 6px solid #2563eb; border-radius: 50%; width: 40px; height: 40px; animation: spin 1s linear infinite; }
        @keyframes spin { 100% { transform: rotate(360deg); } }
    </style>
</head>
<body>
    <h1>Archipel - Démo Sprints & IA Gemini</h1>
    <div class="card">
        <h2>Sprint 1 : Communication 2 nœuds</h2>
        <button onclick="simulateSprint1()">Simuler communication 2 nœuds</button>
        <div class="loader" id="loader-sprint1"></div>
        <div id="sprint1-result"></div>
    </div>
    <div class="card">
        <h2>Sprint 2 : Communication 3 nœuds (offline)</h2>
        <button onclick="simulateSprint2()">Simuler communication 3 nœuds</button>
        <div class="loader" id="loader-sprint2"></div>
        <div id="sprint2-result"></div>
    </div>
    <div class="card">
        <h2>Sprint 3 : Partage de fichier</h2>
        <button onclick="simulateSprint3()">Simuler partage de fichier</button>
        <div class="loader" id="loader-sprint3"></div>
        <div id="sprint3-result"></div>
    </div>
    <div class="card">
        <h2>Tests unitaires Sprints 2 & 3</h2>
        <button onclick="runTest('crypto')">Test Crypto</button>
        <button onclick="runTest('network')">Test Réseau</button>
        <button onclick="runTest('transfer')">Test Transfert</button>
        <div id="result"></div>
    </div>
    <div class="card" id="ia-box">
        <h2>Assistant Gemini IA</h2>
        <input type="text" id="ia-question" placeholder="Pose ta question à Gemini..." size="50">
        <button onclick="askGemini()">Envoyer</button>
        <div id="ia-result"></div>
    </div>
    <script>
        function simulateSprint1() {
            document.getElementById('sprint1-result').innerText = '';
            document.getElementById('loader-sprint1').style.display = 'block';
            fetch('/simulate_sprint1', {
                method: 'POST'
            })
            .then(response => response.json())
            .then(data => {
                document.getElementById('loader-sprint1').style.display = 'none';
                document.getElementById('sprint1-result').innerText = data.result;
            });
        }
        function simulateSprint2() {
            document.getElementById('sprint2-result').innerText = '';
            document.getElementById('loader-sprint2').style.display = 'block';
            fetch('/simulate_sprint2', {
                method: 'POST'
            })
            .then(response => response.json())
            .then(data => {
                document.getElementById('loader-sprint2').style.display = 'none';
                document.getElementById('sprint2-result').innerText = data.result;
            });
        }
        function simulateSprint3() {
            document.getElementById('sprint3-result').innerText = '';
            document.getElementById('loader-sprint3').style.display = 'block';
            fetch('/simulate_sprint3', {
                method: 'POST'
            })
            .then(response => response.json())
            .then(data => {
                document.getElementById('loader-sprint3').style.display = 'none';
                document.getElementById('sprint3-result').innerText = data.result;
            });
        }
        function runTest(type) {
            document.getElementById('result').innerText = 'Test en cours...';
            fetch('/run_test', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ test: type })
            })
            .then(response => response.json())
            .then(data => {
                document.getElementById('result').innerText = data.result;
            });
        }
        function askGemini() {
            var question = document.getElementById('ia-question').value;
            document.getElementById('ia-result').innerText = 'Réponse en cours...';
            fetch('/ask_gemini', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ question: question })
            })
            .then(response => response.json())
            .then(data => {
                document.getElementById('ia-result').innerText = data.result;
            });
        }
    </script>
</body>
</html>
'''

TEST_COMMANDS = {
    'crypto': ['python', '-m', 'unittest', 'crypto/test_secure_channel.py'],
    'network': ['python', '-m', 'unittest', 'network/test_peer_table.py'],
    'transfer': ['python', '-m', 'unittest', 'transfer/test_transfer.py'],
}

@app.route('/')
def index():
    return render_template_string(TEMPLATE)

@app.route('/run_test', methods=['POST'])
def run_test():
    data = request.get_json()
    test_type = data.get('test')
    cmd = TEST_COMMANDS.get(test_type)
    if not cmd:
        return jsonify({'result': 'Test inconnu.'})
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        output = result.stdout + '\n' + result.stderr
    except Exception as e:
        output = f'Erreur lors de l\'exécution du test: {e}'
    return jsonify({'result': output})

@app.route('/ask_gemini', methods=['POST'])
def ask_gemini():
    data = request.get_json()
    question = data.get('question', '')
    # Contexte minimal pour la démo
    context = [f"User: {question}"]
    try:
        from ai.gemini import query_gemini
        result = query_gemini(context, question, api_key=GEMINI_API_KEY)
        if 'error' in result:
            return jsonify({'result': result['error']})
        # Affiche la réponse brute ou le texte principal
        answer = result.get('candidates', [{}])[0].get('content', {}).get('parts', [{}])[0].get('text', str(result))
        return jsonify({'result': answer})
    except Exception as e:
        return jsonify({'result': f'Erreur Gemini: {e}'})
if __name__ == '__main__':
    app.run(debug=True)
