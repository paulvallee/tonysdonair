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
from .pizzas  import PIZZAS
from .toppings import BASE_SAUCES, CHEESES, MEATS, OTHERS, FINISHING_SAUCES, SPICES

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

@app.route('/status')
def status():
    user_id, users = get_user()
    stats = users[user_id]

    mastered = []
    learning = []
    need_help = []

    for p in PIZZAS:
        name = p['name']
        c = stats['correct'][name]
        # categorize by total correct count
        if c >= 3:
            mastered.append(name)
        elif c > 0:
            learning.append(name)
        else:
            need_help.append(name)

    return render_template_string(STATUS_HTML,
        mastered=mastered,
        learning=learning,
        need_help=need_help,
    )

INDEX_HTML = '''
<!doctype html>
<html lang="en" translate="no">
<head>
  <meta http-equiv="Content-Language" content="en">
  <meta name="google" content="notranslate">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <link rel="stylesheet" href="{{ url_for('static', filename='style.css') }}">
  <title>Tony's Pizza Quiz</title>
</head>
<body class="container">
  <h1>Welcome to Tony's Pizza Quiz</h1>
  <form action="/review"><button>Learn</button></form>
  <form action="/quiz"><button>Quiz</button></form>
  <form action="/status"><button>Scores</button></form>    <!-- New button -->
  <form action="/reset"><button>Reset Everything</button></form>
</body>
</html>
'''


# copy code
# In your app.py, update the REVIEW_HTML template to include the HTML skeleton and stylesheet.

REVIEW_HTML = '''
<!doctype html>
<html lang="en" translate="no">
<head>
  <meta http-equiv="Content-Language" content="en">
  <meta name="google" content="notranslate">  
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <link rel="stylesheet" href="{{ url_for('static', filename='style.css') }}">
  <title>Learn {{ pizza.name }}</title>
</head>
<body class="container">
  <h2>{{ pizza.name }}</h2>

  {% if image_url %}
    <img src="{{ image_url }}" alt="{{ pizza.name }}">
  {% endif %}

  <p><em>{{ pizza.mnemonic }}</em></p>
  <p class="stats">Seen: {{ view_count }} |
     Right: {{ correct_count }} |
     Wrong: {{ wrong_count }}</p>

  {% for title, items in sections %}
    <h3>{{ title }}</h3>
    <ul>
      {% for i in items %}
        <li>{{ i }}</li>
      {% endfor %}
    </ul>
  {% endfor %}

  <form action="/quiz"><button {% if not quiz_ready %}disabled{% endif %}>
      Quiz this pizza
  </button></form>
  <form action="/review"><button>Next</button></form>
  <form action="/"><button>Home</button></form>
</body>
</html>
'''

STATUS_HTML = '''
<!doctype html>
<html lang="en" translate="no">
<head>
  <meta http-equiv="Content-Language" content="en">
  <meta name="google" content="notranslate">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <link rel="stylesheet" href="{{ url_for('static', filename='style.css') }}">
  <title>Your Pizza Status</title>
</head>
<body class="container">
  <h2>Your Learning Status</h2>

  <h3>Mastered (3+ correct)</h3>
  {% if mastered %}
    <ul>
      {% for name in mastered %}<li>{{ name }}</li>{% endfor %}
    </ul>
  {% else %}
    <p>You haven’t mastered any pizzas yet.</p>
  {% endif %}

  <h3>Learning (1–2 correct)</h3>
  {% if learning %}
    <ul>
      {% for name in learning %}<li>{{ name }}</li>{% endfor %}
    </ul>
  {% else %}
    <p>You haven’t started learning any pizzas yet.</p>
  {% endif %}

  <h3>Need Help (0 correct)</h3>
  {% if need_help %}
    <ul>
      {% for name in need_help %}<li>{{ name }}</li>{% endfor %}
    </ul>
  {% else %}
    <p>Great job — you have attempted all pizzas!</p>
  {% endif %}

  <div class="nav-buttons">
    <form action="/"><button>Home</button></form>
    <form action="/review"><button>Learn</button></form>
    <form action="/quiz"><button>Quiz</button></form>
  </div>
</body>
</html>
'''



# app.py — Update the QUIZ_HTML template to include HTML skeleton and mobile stylesheet

QUIZ_HTML = '''
<!doctype html>
<html lang="en" translate="no">
<head>
  <meta http-equiv="Content-Language" content="en">
  <meta name="google" content="notranslate">  
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <link rel="stylesheet" href="{{ url_for('static', filename='style.css') }}">
  <title>Quiz {{ pizza.name }}</title>
</head>
<body class="container">
  <h2>Quiz: {{ pizza.name }}</h2>
  <form method="post" action="/submit_quiz">
    {% for title, items in sections %}
      <h3>{{ title }}</h3>
      {% for i in items %}
        <label>
          <input type="checkbox" name="topping" value="{{ i }}"> {{ i }}
        </label>
      {% endfor %}
    {% endfor %}
    <button type="submit">Submit</button>
  </form>
  <form action="/">
    <button>Home</button>
  </form>
</body>
</html>
'''


RESULT_HTML = '''
<!doctype html>
<html lang="en">
<html lang="en" translate="no">
<head>
  <meta http-equiv="Content-Language" content="en">
  <meta name="google" content="notranslate">  
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <link rel="stylesheet" href="{{ url_for('static', filename='style.css') }}">
  <title>Results for {{ pizza.name }}</title>
</head>
<body class="container">
  <h2>Results: {{ pizza.name }}</h2>

  {% if image_url %}
    <img src="{{ image_url }}" alt="{{ pizza.name }}">
  {% endif %}

  <p class="stats">
    Correct Answers: {{ stats.correct[pizza.name] }} |
    Incorrect Answers: {{ stats.wrong[pizza.name] }}
  </p>

  <h3>Outcomes</h3>
  <ul class="outcomes">
    {% for i in correct %}<li>YES {{ i }}</li>{% endfor %}
    {% for i in missed  %}<li>MISSED {{ i }}</li>{% endfor %}
    {% for i in extra   %}<li>NO {{ i }}</li>{% endfor %}
  </ul>

  <h3>Mnemonic</h3>
  <p><em>{{ pizza.mnemonic }}</em></p>

  <div class="nav-buttons">
    <form action="/quiz"><button>Next Quiz</button></form>
    <form action="/"><button>Home</button></form>
  </div>
</body>
</html>
'''



# --- Main ---
if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
