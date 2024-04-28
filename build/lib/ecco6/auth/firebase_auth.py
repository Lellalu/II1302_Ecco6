import json
import logging
import os
import requests
import streamlit as st
import firebase_admin
from firebase_admin import auth, exceptions, credentials, initialize_app
import asyncio
from httpx_oauth.clients.google import GoogleOAuth2
import webbrowser

## -------------------------------------------------------------------------------------------------
## Firebase Auth API -------------------------------------------------------------------------------
## -------------------------------------------------------------------------------------------------

def sign_in_with_email_and_password(email, password):
    request_ref = "https://www.googleapis.com/identitytoolkit/v3/relyingparty/verifyPassword?key={0}".format(st.secrets['FIREBASE_WEB_API_KEY'])
    headers = {"content-type": "application/json; charset=UTF-8"}
    data = json.dumps({"email": email, "password": password, "returnSecureToken": True})
    request_object = requests.post(request_ref, headers=headers, data=data)
    raise_detailed_error(request_object)
    return request_object.json()

def get_account_info(id_token):
    request_ref = "https://www.googleapis.com/identitytoolkit/v3/relyingparty/getAccountInfo?key={0}".format(st.secrets['FIREBASE_WEB_API_KEY'])
    headers = {"content-type": "application/json; charset=UTF-8"}
    data = json.dumps({"idToken": id_token})
    request_object = requests.post(request_ref, headers=headers, data=data)
    raise_detailed_error(request_object)
    return request_object.json()

def send_email_verification(id_token):
    request_ref = "https://www.googleapis.com/identitytoolkit/v3/relyingparty/getOobConfirmationCode?key={0}".format(st.secrets['FIREBASE_WEB_API_KEY'])
    headers = {"content-type": "application/json; charset=UTF-8"}
    data = json.dumps({"requestType": "VERIFY_EMAIL", "idToken": id_token})
    request_object = requests.post(request_ref, headers=headers, data=data)
    raise_detailed_error(request_object)
    return request_object.json()

def send_password_reset_email(email):
    request_ref = "https://www.googleapis.com/identitytoolkit/v3/relyingparty/getOobConfirmationCode?key={0}".format(st.secrets['FIREBASE_WEB_API_KEY'])
    headers = {"content-type": "application/json; charset=UTF-8"}
    data = json.dumps({"requestType": "PASSWORD_RESET", "email": email})
    request_object = requests.post(request_ref, headers=headers, data=data)
    raise_detailed_error(request_object)
    return request_object.json()

def create_user_with_email_and_password(email, password):
    request_ref = "https://www.googleapis.com/identitytoolkit/v3/relyingparty/signupNewUser?key={0}".format(st.secrets['FIREBASE_WEB_API_KEY'])
    headers = {"content-type": "application/json; charset=UTF-8" }
    data = json.dumps({"email": email, "password": password, "returnSecureToken": True})
    request_object = requests.post(request_ref, headers=headers, data=data)
    raise_detailed_error(request_object)
    return request_object.json()

def delete_user_account(id_token):
    request_ref = "https://www.googleapis.com/identitytoolkit/v3/relyingparty/deleteAccount?key={0}".format(st.secrets['FIREBASE_WEB_API_KEY'])
    headers = {"content-type": "application/json; charset=UTF-8"}
    data = json.dumps({"idToken": id_token})
    request_object = requests.post(request_ref, headers=headers, data=data)
    raise_detailed_error(request_object)
    return request_object.json()

def raise_detailed_error(request_object):
    try:
        request_object.raise_for_status()
    except requests.exceptions.HTTPError as error:
        raise requests.exceptions.HTTPError(error, request_object.text)

## -------------------------------------------------------------------------------------------------
## Authentication functions ------------------------------------------------------------------------
## -------------------------------------------------------------------------------------------------

# Initialize Firebase app
current_dir = os.path.dirname(__file__)
service_account_key_path = os.path.join(current_dir, "../firebase_credentials.json")
cred = credentials.Certificate(service_account_key_path)
try:
    logging.info("Initializing Firebase app...")  
    firebase_admin.get_app()
    logging.info("Firebase app initialized successfully.")  
except ValueError as e:
    logging.error("Error initializing Firebase app: %s", e)  
    initialize_app(cred)

# Initialize Google OAuth2 client
client_id = st.secrets["GOOGLE_AUTH"]["CLIENT_ID"] 
client_secret = st.secrets["GOOGLE_AUTH"]["CLIENT_SECRET"]
redirect_url = "http://localhost:8501"  # Your redirect URL

client = GoogleOAuth2(client_id=client_id, client_secret=client_secret)


def sign_in(email:str, password:str) -> None:
    try:
        # Attempt to sign in with email and password
        id_token = sign_in_with_email_and_password(email,password)['idToken']

        # Get account information
        user_info = get_account_info(id_token)["users"][0]

        # If email is not verified, send verification email and do not sign in
        if not user_info["emailVerified"]:
            send_email_verification(id_token)
            st.session_state.auth_warning = 'Check your email to verify your account'

        # Save user info to session state and rerun
        else:
            st.session_state.user_info = user_info
            st.experimental_rerun()

    except requests.exceptions.HTTPError as error:
        error_message = json.loads(error.args[1])['error']['message']
        if error_message in {"INVALID_EMAIL","EMAIL_NOT_FOUND","INVALID_PASSWORD","MISSING_PASSWORD"}:
            st.session_state.auth_warning = 'Error: Use a valid email and password'
        else:
            st.session_state.auth_warning = 'Error: Please try again later'

    except Exception as error:
        print(error)
        st.session_state.auth_warning = 'Error: Please try again later'


def create_account(email:str, password:str) -> None:
    try:
        # Create account (and save id_token)
        id_token = create_user_with_email_and_password(email,password)['idToken']

        # Create account and send email verification
        send_email_verification(id_token)
        st.session_state.auth_success = 'Check your inbox to verify your email'
    
    except requests.exceptions.HTTPError as error:
        error_message = json.loads(error.args[1])['error']['message']
        if error_message == "EMAIL_EXISTS":
            st.session_state.auth_warning = 'Error: Email belongs to existing account'
        elif error_message in {"INVALID_EMAIL","INVALID_PASSWORD","MISSING_PASSWORD","MISSING_EMAIL","WEAK_PASSWORD"}:
            st.session_state.auth_warning = 'Error: Use a valid email and password'
        else:
            st.session_state.auth_warning = 'Error: Please try again later'
    
    except Exception as error:
        print(error)
        st.session_state.auth_warning = 'Error: Please try again later'


def reset_password(email:str) -> None:
    try:
        send_password_reset_email(email)
        st.session_state.auth_success = 'Password reset link sent to your email'
    
    except requests.exceptions.HTTPError as error:
        error_message = json.loads(error.args[1])['error']['message']
        if error_message in {"MISSING_EMAIL","INVALID_EMAIL","EMAIL_NOT_FOUND"}:
            st.session_state.auth_warning = 'Error: Use a valid email'
        else:
            st.session_state.auth_warning = 'Error: Please try again later'    
    
    except Exception:
        st.session_state.auth_warning = 'Error: Please try again later'


def sign_out() -> None:
    st.session_state.clear()
    st.session_state.auth_success = 'You have successfully signed out'


def delete_account(password:str) -> None:
    try:
        # Confirm email and password by signing in (and save id_token)
        id_token = sign_in_with_email_and_password(st.session_state.user_info['email'],password)['idToken']
        
        # Attempt to delete account
        delete_user_account(id_token)
        st.session_state.clear()
        st.session_state.auth_success = 'You have successfully deleted your account'

    except requests.exceptions.HTTPError as error:
        error_message = json.loads(error.args[1])['error']['message']
        print(error_message)

    except Exception as error:
        print(error)


async def get_access_token(client: GoogleOAuth2, redirect_url: str, code: str):
    logging.info("Getting access token...")  
    return await client.get_access_token(code, redirect_url)

async def get_email(client: GoogleOAuth2, token: str):
    logging.info("Getting user email...")  
    user_id, user_email = await client.get_id_email(token)
    return user_id, user_email

def get_logged_in_user_email():
    try:
        code = st.query_params.get('code')  # Remove the parentheses
        if code:
            print("Received authorization code:", code)
            token = asyncio.run(get_access_token(client, redirect_url, code))
            print("Received access token:", token)
            st.session_state.google_auth_code = code  # Set google_auth_code in session state
            st.query_params.clear()

            if token:
                user_id, user_email = asyncio.run(get_email(client, token['access_token']))
                print("Received user email:", user_email)
                if user_email:
                    try:
                        user = auth.get_user_by_email(user_email)
                    except exceptions.FirebaseError:
                        user = auth.create_user(email=user_email)
                    st.session_state.email = user.email
                    st.session_state.user_info = {"user_id": user.uid, "user_email": user.email}  # Set user_info in session state
                    return user.email
        return None
    except Exception as e:
        print("Error in get_logged_in_user_email:", e)
        pass


def show_login_button():
    authorization_url = asyncio.run(client.get_authorization_url(
        redirect_url,
        scope=["email", "profile"],
        extras_params={"access_type": "offline"},
    ))
    st.markdown(f'<a href="{authorization_url}" target="_self">Login</a>', unsafe_allow_html=True)
    get_logged_in_user_email()


# Define your authorization URL
authorization_url = asyncio.run(client.get_authorization_url(
    redirect_url,
    scope=["email", "profile"],
    extras_params={"access_type": "offline"},
))

def redirect_and_call_function():
    webbrowser.open(authorization_url)
    get_logged_in_user_email()


