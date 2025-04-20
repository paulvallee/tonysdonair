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

DATA_FILE = 'user_data.json'
app = Flask(__name__)
app.secret_key = os.urandom(24)

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
            'views': {p['name']: 0 for p in PIZZAS},
            'correct': {p['name']: 0 for p in PIZZAS},
            'wrong':   {p['name']: 0 for p in PIZZAS},
            'history': []
        }
        save_user_data(users)
    return user_id, users

@app.route('/')
def index():
    user_id, users = get_user()
    resp = make_response(render_template_string(INDEX_HTML))
    resp.set_cookie('user_id', user_id)
    return resp

@app.route('/reset')
def reset():
    resp = make_response(redirect(url_for('index')))
    resp.set_cookie('user_id', '', expires=0)
    return resp

@app.route('/review')
def review():
    user_id, users = get_user()
    users[user_id]['current'] = random.choice(PIZZAS)['name']
    pizza = next(p for p in PIZZAS if p['name']==users[user_id]['current'])
    users[user_id]['views'][pizza['name']] += 1
    save_user_data(users)

    # build sections only if used
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

    quiz_ready = users[user_id]['views'][pizza['name']] >= 3
    resp = make_response(render_template_string(REVIEW_HTML,
        pizza=pizza, sections=sections, quiz_ready=quiz_ready))
    resp.set_cookie('user_id', user_id)
    return resp

@app.route('/quiz')
def quiz():
    user_id, users = get_user()
    stats = users[user_id]
    last5 = stats['history'][-5:]
    candidates = [p for p in PIZZAS if p['name'] not in last5]
    if not candidates:
        candidates = PIZZAS
    weights = []
    for p in candidates:
        name = p['name']
        total = stats['correct'][name] + stats['wrong'][name]
        weights.append((stats['wrong'][name] + 1) / (total + 2))
    pizza = random.choices(candidates, weights=weights, k=1)[0]
    stats['current'] = pizza['name']
    save_user_data(users)

    # same section logic
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

    resp = make_response(render_template_string(QUIZ_HTML,
        pizza=pizza, sections=sections))
    resp.set_cookie('user_id', user_id)
    return resp

@app.route('/submit_quiz', methods=['POST'])
def submit_quiz():
    user_id, users = get_user()
    stats = users[user_id]
    name = stats.get('current')
    pizza = next(p for p in PIZZAS if p['name']==name)
    picked = set(request.form.getlist('topping'))
    actual = set(pizza['toppings'])

    if picked == actual:
        stats['correct'][name] += 1
    else:
        stats['wrong'][name] += 1
    stats['history'].append(name)
    if len(stats['history']) > 5:
        stats['history'] = stats['history'][-5:]
    save_user_data(users)

    correct = sorted(actual & picked)
    missed  = sorted(actual - picked)
    extra   = sorted(picked - actual)

    # rebuild sections for display
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

    resp = make_response(render_template_string(RESULT_HTML,
        pizza=pizza,
        stats=stats,
        correct=correct, missed=missed, extra=extra,
        sections=sections))
    resp.set_cookie('user_id', user_id)
    return resp

# --- HTML Templates ---

INDEX_HTML = '''
<!doctype html>
<title>Tony’s Pizza Quiz</title>
<h1>Welcome to Tony’s Pizza Quiz</h1>
<form action="/review"><button>Review</button></form>
<form action="/quiz"><button>Quiz</button></form>
<form action="/reset"><button>Reset Everything</button></form>
'''

REVIEW_HTML = '''
<!doctype html>
<title>Review {{ pizza.name }}</title>
<h2>{{ pizza.name }}</h2>
<p><em>{{ pizza.mnemonic }}</em></p>
{% for title, items in sections %}
  <h3>{{ title }}</h3>
  <ul>{% for i in items %}<li>{{ i }}</li>{% endfor %}</ul>
{% endfor %}
<form action="/quiz"><button {% if not quiz_ready %}disabled{% endif %}>
    Quiz this pizza
</button></form>
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
      <label><input type="checkbox" name="topping" value="{{ i }}"> {{ i }}</label><br>
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
<p>Seen: {{ stats.views[pizza.name] }} |
   Right: {{ stats.correct[pizza.name] }} |
   Wrong: {{ stats.wrong[pizza.name] }}</p>
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

if __name__ == '__main__':
    app.run(debug=True)
