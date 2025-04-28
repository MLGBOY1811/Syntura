from flask import Flask, redirect, url_for, session, request, jsonify
from flask import render_template
from datetime import datetime
from flask_session import Session
from oauthlib.oauth2 import WebApplicationClient
import sqlite3
import json
import requests
import os


os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'
GOOGLE_CLIENT_ID = "600581126647-e89kfeu6rc0fq2cils3sk7t909ji1obm.apps.googleusercontent.com"
GOOGLE_CLIENT_SECRET ="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"
GOOGLE_DISCOVERY_URL = "https://accounts.google.com/.well-known/openid-configuration"

app = Flask(__name__)

app.secret_key = os.urandom(24)
app.config['SESSION_TYPE'] = 'filesystem'
app.config['SESSION_PERMANENT'] = False

Session(app)

client = WebApplicationClient(GOOGLE_CLIENT_ID)
def get_google_provider_cfg():
    return requests.get(GOOGLE_DISCOVERY_URL).json()


# Home Page route
@app.route("/")
def home():
    if 'user' in session:
        return render_template('main.html', user=session['user'])
    else:
        return render_template("home.html")


@app.route("/login")
def login():
    google_provider_cfg = get_google_provider_cfg()

    authorization_endpoint = google_provider_cfg['authorization_endpoint']
    request_uri = client.prepare_request_uri(
        authorization_endpoint,
        redirect_uri = request.base_url + "/callback",
        scope = ['openid','email','profile']
    )
    return redirect(request_uri)


@app.route("/login/callback")
def callback():
    code = request.args.get('code')
    google_provider_cfg = get_google_provider_cfg()
    token_endpoint = google_provider_cfg['token_endpoint']
    token_url, headers, body = client.prepare_token_request(
        token_endpoint,
        authorization_response=request.url,
        redirect_url=request.base_url,
        code=code
    )
    token_response = requests.post(
        token_url,
        headers=headers,
        data=body,
        auth = (GOOGLE_CLIENT_ID,GOOGLE_CLIENT_SECRET)
    )
    client.parse_request_body_response(json.dumps(token_response.json()))
    userinfo_endpoint = google_provider_cfg['userinfo_endpoint']
    uri,headers,body = client.add_token(userinfo_endpoint)
    userinfo_response = requests.get(uri,headers=headers,data=body)

    if userinfo_response.json().get('email_verified'):
        unique_id = userinfo_response.json()["sub"]
        users_email = userinfo_response.json()["email"]
        picture = userinfo_response.json()["picture"]
        users_name = userinfo_response.json()["given_name"]

        # store the user information in the session

        session['user'] = {
            "id" : unique_id,
            "email" : users_email,
            "name" : users_name,
            "picture" : picture,
            "LastLogin" : ""
        }
        #store in the database
        with sqlite3.connect('database.db') as con:
            cur = con.cursor()
            response = cur.execute("SELECT id, LastLogin FROM users WHERE id=?", (unique_id,))
            fetched = response.fetchall()

            if fetched:
                # User exists
                session['user']["LastLogin"] = fetched[0][1]
                cur.execute("UPDATE users SET LastLogin= DateTime('now','localtime') WHERE id ='"+ unique_id + "'")
                con.commit()

            else:
                # User does not exist
                cur.execute("INSERT INTO users (id, email, name, picture, LastLogin) VALUES (?,?,?,?,DateTime('now','localtime'))",
                            (unique_id, users_email, users_name, picture))
                con.commit()
                session['user']["LastLogin"] = "New User"
        return render_template('main.html', user=session['user'])
    else:
        return "user email not available", 400
    # Route to form used to add a new student to the database


@app.route('/oauth2callback')
def oauth2callback():
    if not session['state'] == request.args['state']:
        return 'Invalid state parameter', 400
    oauth_flow.fetch_token(authorization_response=request.url.replace('http:', 'https:'))
    session['access_token'] = oauth_flow.credentials.token
    return redirect("/")


@app.route('/dashboard')
def dashboard():
    if 'user' in session:
        user = session['user']
        return f"Welcome, {user['name']}"
    else:
        return redirect('/logout')


@app.route('/appointments')
def appointments():
    return "Appointments tab under construction"
    # return render_template("appointments.html")


@app.route('/patients')
def patients():
    return "Patients tab under construction"
    # return render_template("patients.html")


@app.route('/treatments')
def treatments():
    return "Treatments tab under construction"
    # return render_template("treatments.html")


@app.route('/contact')
def contact():
    return "Contact tab under construction"
    # return render_template("message.html")


@app.route('/sales')
def sales():
    return "Sales tab under construction"
    # return render_template("sales.html")


@app.route('/account', methods=['GET'])
def account():
    if 'user' in session:
        id = session['user']['id']
        with sqlite3.connect('database.db') as con:
            cur = con.cursor()
            response = cur.execute("""
                SELECT picture, email, phoneNumber, address, dob, department 
                FROM users 
                WHERE id=?
            """, (id,))
            fetched = response.fetchone()
            if fetched:
                profile_picture_url = fetched[0]
                email = fetched[1]
                phone_number = fetched[2]
                address = fetched[3]
                dob = fetched[4]
                department = fetched[5]
                if dob:
                    formatted_dob = datetime.strptime(dob, '%d/%m/%Y').strftime('%Y-%m-%d')
                else:
                    formatted_dob = None
                return render_template(
                    "account.html",
                    profile_picture_url=profile_picture_url,
                    email=email,
                    user_name=session['user']['name'],
                    phone_number=phone_number,
                    address=address,
                    dob=formatted_dob,
                    department=department
                )
            else:
                return redirect('/')
    else:
        return redirect('/')

@app.route('/update_account', methods=['POST'])
def update_account():
    if 'user' in session:
        id = session['user']['id']
        with sqlite3.connect('database.db') as con:
            cur = con.cursor()
            dob = request.form['dob']
            formatted_dob = (
                datetime.strptime(dob, '%Y-%m-%d').strftime('%d/%m/%Y')
                if dob else None
            )
            cur.execute("""
                UPDATE users 
                SET email=?, phoneNumber=?, address=?, dob=?, department=? 
                WHERE id=?
            """, (
                request.form['email'],
                request.form['phone'],
                request.form['address'],
                formatted_dob,
                request.form['department'],
                id
            ))
            con.commit()
        return redirect('/')
    else:
        return redirect('/')


@app.route('/delete_account', methods=['POST'])
def delete_account():
    if 'user' in session:
        id = session['user']['id']
        with sqlite3.connect('database.db') as con:
            cur = con.cursor()
            # Delete user data from the database
            cur.execute("""
                DELETE FROM users
                WHERE id=?
            """, (id,))
            con.commit()
        session.pop('user', None)
        return redirect('/logout')
    else:
        return redirect('/')


@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')


if __name__ == "__main__":
    app.run(debug=True, port=3000)
