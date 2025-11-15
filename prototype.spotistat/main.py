import os
from flask import Flask, redirect, request, session, url_for, render_template
import spotipy
from spotipy.oauth2 import SpotifyOAuth
from datetime import datetime

app = Flask(__name__)
# Secret key for sessions — set as environment variable on Render
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-change-me")

# Read Spotify credentials from environment variables
CLIENT_ID = os.environ.get("SPOTIFY_CLIENT_ID")
CLIENT_SECRET = os.environ.get("SPOTIFY_CLIENT_SECRET")
REDIRECT_URI = os.environ.get("SPOTIFY_REDIRECT_URI")

# Scope needed for reading recent tracks
SCOPE = "user-read-recently-played user-read-private"

def make_oauth():
    """Creates a SpotifyOAuth object with environment variable config."""
    return SpotifyOAuth(
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET,
        redirect_uri=REDIRECT_URI,
        scope=SCOPE,
        cache_path=None  # No file caching for prototype
    )

@app.route("/")
def index():
    """Home page — shows login button or link to recent track page."""
    logged_in = "token_info" in session
    return render_template("login.html", logged_in=logged_in)

@app.route("/login")
def login():
    """Redirects user to Spotify's authorization page."""
    oauth = make_oauth()
    auth_url = oauth.get_authorize_url()
    return redirect(auth_url)

@app.route("/callback")
def callback():
    """Handles Spotify OAuth redirect + retrieves access token."""
    oauth = make_oauth()
    code = request.args.get("code")

    if code is None:
        error = request.args.get("error", "Authorization failed")
        return f"Error during login: {error}", 400

    token_info = oauth.get_access_token(code)
    session["token_info"] = token_info
    return redirect(url_for("recent"))

@app.route("/recent")
def recent():
    """Fetch most recent played track & display it."""
    token_info = session.get("token_info")
    if not token_info:
        return redirect(url_for("index"))

    access_token = token_info.get("access_token")
    if not access_token:
        return "Missing access token.", 400

    sp = spotipy.Spotify(auth=access_token)

    # Get most recent track (limit 1)
    results = sp.current_user_recently_played(limit=1)
    items = results.get("items", [])

    if not items:
        return render_template("recent.html", track=None, user=None)

    item = items[0]
    track = item["track"]
    track_name = track.get("name")
    artists = ", ".join([a["name"] for a in track.get("artists", [])])
    played_at_raw = item.get("played_at")

    # Convert timestamp to readable format
    try:
        played_at = datetime.fromisoformat(played_at_raw.replace("Z", "+00:00"))
        played_at_str = played_at.strftime("%Y-%m-%d %H:%M:%S UTC")
    except Exception:
        played_at_str = played_at_raw

    # Fetch user profile for display name
    user_profile = sp.me()
    display_name = user_profile.get("display_name", user_profile.get("id"))

    return render_template(
        "recent.html",
        track={
            "name": track_name,
            "artists": artists,
            "played_at": played_at_str
        },
        user={"display_name": display_name}
    )

@app.route("/logout")
def logout():
    """Clears session + logs user out."""
    session.clear()
    return redirect(url_for("index"))

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8888))
    app.run(host="0.0.0.0", port=port, debug=True)
