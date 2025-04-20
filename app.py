# copy code
#!/usr/bin/env python3
# app.py — Tony’s Pizza Quiz Web App (Flask)

import os
import json
import uuid
import random
from flask import (
    Flask, request, redirect, url_for,
    make_response, render_template_string
)
from pizzas import PIZZAS
from toppings import BASE_SAUCES, CHEESES, MEATS, OTHERS, FINISHING_SAUCES, SPICES

# --- Configuration ---
DATA_FILE = 'user_data.json'
app = Flask(__name__, static_folder='static')
app.secret_key = os.urandom(24)

# --- Persistence Helpers ---
def load_user_data():
    if os.path.exists(DATA_FILE):
        return json.load(open(DATA_FILE))
    return {}

def save_user_data(data):
    with open(DATA_FILE, 'w') as f:
        json.dump(data, f)

def get_user():
    users = load_user_data()
    user_id = request.cookies.get('user_id')
    if not user_id or user_id not in users:
        user_id = str(uuid.uuid4())
        users[user_id] = {
            'views':   {p['name']: 0 for p in PIZZAS},
            'correct': {p['name']: 0 for p in PIZZAS},
            'wrong':   {p['name']: 0 for p in PIZZAS},
            'history': []
        }
        save_user_data(users)
    return user_id, users

# --- Routes ---
@app.route('/')
def index():
    user_id, _ = get_user()
    resp = make_response(render_template_string(INDEX_HTML))
    resp.set_cookie('user_id', user_id)
    return resp

@app.route('/reset')
def reset():
    resp = make_response(redirect(url_for('index')))
    resp.set_cookie('user_id', '', expires=0)
    return resp

# --- review() route ---
@app.route('/review')
def review():
    user_id, users = get_user()
    pizza = random.choice(PIZZAS)
    name = pizza['name']
    users[user_id]['current'] = name
    users[user_id]['views'][name] += 1
    save_user_data(users)

    # counts for display
    view_count    = users[user_id]['views'][name]
    correct_count = users[user_id]['correct'][name]
    wrong_count   = users[user_id]['wrong'][name]

    # build only used sections
    sections = []
    for title, bucket in [
        ("Base Sauces", BASE_SAUCES),
        ("Cheeses", CHEESES),
        ("Meats", MEATS),
        ("Other Toppings", OTHERS),
        ("Finishing Sauces", FINISHING_SAUCES),
        ("Spices", SPICES),
    ]:
        items = [t for t in pizza['toppings'] if t in bucket]
        if items:
            sections.append((title, items))

    # check for image
    filename = f"{name}.png"
    image_url = None
    if os.path.exists(os.path.join(app.static_folder, filename)):
        image_url = url_for('static', filename=filename)

    quiz_ready = view_count >= 3

    resp = make_response(render_template_string(REVIEW_HTML,
        pizza=pizza,
        sections=sections,
        quiz_ready=quiz_ready,
        image_url=image_url,
        view_count=view_count,
        correct_count=correct_count,
        wrong_count=wrong_count
    ))
    resp.set_cookie('user_id', user_id)
    return resp

@app.route('/quiz')
def quiz():
    user_id, users = get_user()
    stats = users[user_id]

    # pick pizza (exclude last 5)
    last5 = stats['history'][-5:]
    candidates = [p for p in PIZZAS if p['name'] not in last5] or PIZZAS
    weights = [
        (stats['wrong'][p['name']] + 1) /
        (stats['correct'][p['name']] + stats['wrong'][p['name']] + 2)
        for p in candidates
    ]
    pizza = random.choices(candidates, weights=weights, k=1)[0]
    stats['current'] = pizza['name']
    save_user_data(users)

    # always show all sections
    sections = [
        ("Base Sauces",      BASE_SAUCES),
        ("Cheeses",          CHEESES),
        ("Meats",            MEATS),
        ("Other Toppings",   OTHERS),
        ("Finishing Sauces", FINISHING_SAUCES),
        ("Spices",           SPICES),
    ]
    resp = make_response(render_template_string(QUIZ_HTML,
        pizza=pizza,
        sections=sections
    ))
    resp.set_cookie('user_id', user_id)
    return resp

@app.route('/submit_quiz', methods=['POST'])
def submit_quiz():
    user_id, users = get_user()
    stats = users[user_id]
    name = stats['current']
    pizza = next(p for p in PIZZAS if p['name'] == name)

    # compute image URL same as in review
    filename = f"{name}.png"
    image_url = None
    if os.path.exists(os.path.join(app.static_folder, filename)):
        image_url = url_for('static', filename=filename)

    picked = set(request.form.getlist('topping'))
    actual = set(pizza['toppings'])

    if picked == actual:
        stats['correct'][name] += 1
    else:
        stats['wrong'][name] += 1

    stats['history'].append(name)
    stats['history'] = stats['history'][-5:]
    save_user_data(users)

    correct = sorted(actual & picked)
    missed  = sorted(actual - picked)
    extra   = sorted(picked - actual)

    resp = make_response(render_template_string(RESULT_HTML,
        pizza=pizza,
        stats=stats,
        correct=correct,
        missed=missed,
        extra=extra,
        image_url=image_url
    ))
    resp.set_cookie('user_id', user_id)
    return resp

# --- HTML Templates ---
# --- Home page (INDEX_HTML) ---
INDEX_HTML = '''
<!doctype html>
<title>Tony’s Pizza Quiz</title>
<h1>Welcome to Tony’s Pizza Quiz</h1>
<form action="/review"><button>Learn</button></form>
<form action="/quiz"><button>Quiz</button></form>
<form action="/reset"><button>Reset Everything</button></form>
'''

REVIEW_HTML = '''
<!doctype html>
<title>Learn {{ pizza.name }}</title>
<h2>{{ pizza.name }}</h2>
{% if image_url %}
  <img src="{{ image_url }}" alt="{{ pizza.name }}"
       style="max-width:400px; margin-bottom:1em;">
{% endif %}

<p><em>{{ pizza.mnemonic }}</em></p>
<p>Seen: {{ view_count }} |
   Right: {{ correct_count }} |
   Wrong: {{ wrong_count }}</p>

{% for title, items in sections %}
  <h3>{{ title }}</h3>
  <ul>{% for i in items %}<li>{{ i }}</li>{% endfor %}</ul>
{% endfor %}

<form action="/quiz">
  <button {% if not quiz_ready %}disabled{% endif %}>Quiz this pizza</button>
</form>
<form action="/review"><button>Next</button></form>
<form action="/"><button>Home</button></form>
'''

QUIZ_HTML = '''
<!doctype html>
<title>Quiz {{ pizza.name }}</title>
<h2>Quiz: {{ pizza.name }}</h2>
<form method="post" action="/submit_quiz">
  {% for title, items in sections %}
    <h3>{{ title }}</h3>
    {% for i in items %}
      <label>
        <input type="checkbox" name="topping" value="{{ i }}"> {{ i }}
      </label><br>
    {% endfor %}
  {% endfor %}
  <button type="submit">Submit</button>
</form>
<form action="/"><button>Home</button></form>
'''

RESULT_HTML = '''
<!doctype html>
<title>Results for {{ pizza.name }}</title>
<h2>Results: {{ pizza.name }}</h2>

{% if image_url %}
  <img src="{{ image_url }}" alt="{{ pizza.name }}"
       style="max-width:400px; margin-bottom:1em;">
{% endif %}

<p>Correct Answers: {{ stats.correct[pizza.name] }} |
   Incorrect Answers: {{ stats.wrong[pizza.name] }}</p>

<h3>Outcomes</h3>
<ul>
  {% for i in correct %}<li>YES {{ i }}</li>{% endfor %}
  {% for i in missed  %}<li>MISSED {{ i }}</li>{% endfor %}
  {% for i in extra   %}<li>NO {{ i }}</li>{% endfor %}
</ul>

<h3>Mnemonic</h3>
<p><em>{{ pizza.mnemonic }}</em></p>

<form action="/quiz"><button>Next Quiz</button></form>
<form action="/"><button>Home</button></form>
'''

# --- Main ---
if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
