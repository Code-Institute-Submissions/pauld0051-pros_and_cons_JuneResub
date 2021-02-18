import os
import ctypes
import json
from flask import (
    Flask, flash, render_template, 
    redirect, request, session, url_for)
from flask_pymongo import PyMongo
from bson.objectid import ObjectId
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
if os.path.exists("env.py"):
    import env


app = Flask (__name__)

app.config["MONGO_DBNAME"] = os.environ.get("MONGO_DBNAME")
app.config["MONGO_URI"] = os.environ.get("MONGO_URI")
app.secret_key = os.environ.get("SECRET_KEY")

mongo = PyMongo(app)


@app.route("/")
@app.route("/get_questions")
def get_questions():
    admin = "9dyhnxe8u4"
    questions = list(mongo.db.questions.find().sort("_id", -1))
    created_by = [created_by['created_by'] for created_by in questions]
    is_friends = [is_friends['is_friends'] for is_friends in questions]  
    
    if "user" in session:
        profile = mongo.db.users.find_one({"username": session["user"]}) # Get the session user for _id matching
        profile_friends = profile["friends"] # Get the list of ObjectId from the friends array under the session user's profile
        friends = mongo.db.users.find({"_id": {"$in": profile_friends}}) # Insert each ObjectId to get the friend's user profile
        friend_list = [friend['username'] for friend in friends] # For each of the ObjectId find the username associated
        matched = [matched for matched in created_by if matched in friend_list] # Look to see if any friends match to the created_by list
        matched = list(dict.fromkeys(matched)) # Remove duplicates from the list
     
        return render_template("questions.html", questions=questions, admin=admin, matched=matched)

    else: # If user is not logged in then no need to match for friendships
        return render_template("questions.html", questions=questions, admin=admin)


@app.route("/filters", methods=["GET", "POST"])
def filters():
    sort = request.form.get("sort", "latest")
    if sort == "oldest":
        questions = list(mongo.db.questions.find().sort("_id", 1))
    if sort == "latest":
        questions = list(mongo.db.questions.find().sort("added_on", -1))
    if sort == "names":
        questions = list(mongo.db.questions.find().sort("created_by", 1))
    
    return render_template("questions.html", questions=questions)


@app.route("/filter_name", methods=["GET", "POST"])
def filter_name():
    names = session["user"]
    questions = mongo.db.questions.find(
        {"created_by": session["user"]})
    return render_template("filter_name.html", questions=questions)


@app.route("/search", methods=["GET", "POST"])
def search():
    query = request.form.get("query")
    questions = list(mongo.db.questions.find({"$text": {"$search": query}}))     
    return render_template("questions.html", questions=questions)


@app.route("/search_profiles", methods=["GET", "POST"])
def search_profiles():
    if "user" in session:
        user = session["user"] or None
        user_profile = mongo.db.users.find_one({"username": user})
        search_profiles = request.form.get("search_profiles")
        profiles = mongo.db.users.find({"$text": {"$search": search_profiles}})

        # Check if the logged in user is friends with any of the found profiles
        # Check all the profiles that are found against current friends
    
        searched_profiles = list(mongo.db.users.find({"$text": {"$search": search_profiles}}))
        profile_usernames = []
        
        for username in searched_profiles:
            profile_usernames.append(username["username"]) # Find a list of all the names that came up in the search
        profile_friends = user_profile["friends"] # Get the list of ObjectId from the friends array under the session user's profile
    
        friends = mongo.db.users.find({"_id": {"$in": profile_friends}}) # Insert each ObjectId to get the friend's user profile
        friend_list = [friend['username'] for friend in friends] # For each of the ObjectId find the username associated
        matched = [matched for matched in profile_usernames if matched in friend_list] # Look to see if any friends match to the created_by list
        matched = list(dict.fromkeys(matched)) # Remove duplicates from the list
        # Check if there is a pending friends request from the logged in user (display pause)
        from_user = list(mongo.db.friend_requests.find({"friend_request_from": user_profile["username"]})) 
        request_from = []
        for profile in from_user:
            request_from.append(profile["friend_request_to"]) # For each request to a profile
        requested = [requested for requested in profile_usernames if requested in request_from]
        # Check if there is a pending friends request from the found profiles (allow accept or decline)
        to_user = list(mongo.db.friend_requests.find({"friend_request_to": user_profile["username"]}))
        request_to = []
        for profile in to_user:
            request_to.append(profile["friend_request_from"]) # For each request from a profile
        requested_to = [requested_to for requested_to in profile_usernames if requested_to in request_to]
        # For everything else allow logged in user to send a friend request
        result_list = []
        send_request = False # Default state
        for one_profile in profile_usernames:
            if (one_profile in matched) or (one_profile in requested) or (one_profile in requested_to):
                result_list.append((one_profile,True))
            else:
                result_list.append((one_profile,False))

        return render_template("search_profiles.html", profiles=profiles, user=user_profile, friends=matched, 
        requested=requested, requested_to=requested_to, result_list=result_list)
    else:
        return redirect(url_for("login")) 


@app.route("/view_profile/<profile>", methods=["GET", "POST"])
def view_profile(profile):
    admin = "9dyhnxe8u4"
    user_profile = mongo.db.users.find_one({"username": profile})
    username = user_profile["username"]
    questions = list(mongo.db.questions.find(
        {"created_by": username}))
    if "user" not in session:
        return render_template("view_profile.html", profile=user_profile, questions=questions)
    current_user = mongo.db.users.find_one({"username": session["user"]})
    logged_in_user = current_user["username"]
    if logged_in_user != user_profile["username"]:
        # If user is logged in, they can add friends etc
        # check to see if users are already friends with this profile
        already_friends = mongo.db.friends.find_one({'$or':
        [
            {'$and':[{"is_friends_1": current_user["username"]},
            {"is_friends_2": username}]},
            {'$and':[{"is_friends_1": username},
            {"is_friends_2": current_user["username"]}]}
        ]})
        # check to see if user has sent a friend request to this profile
        pending_request = mongo.db.friend_requests.find_one({'$or':
        [
            {'$and':[{"friend_request_from": current_user["username"]},
            {"friend_request_to": username}]},
            {'$and':[{"friend_request_from": username},
            {"friend_request_to": current_user["username"]}]}        
        ]})
        # Check to see if logged in user is trying to "view" their profile and redirect them to "profile"
        return render_template("view_profile.html", profile=user_profile, 
        friends=already_friends, pending_request=pending_request, user=logged_in_user, 
        questions=questions, admin=admin)
    #  If user is logged in, they get to see their own profile   
    else:
        return redirect(url_for("profile", username=logged_in_user))


@app.route("/remove_friend/<profile>", methods=["GET", "POST"])
def remove_friend(profile):
    user_profile = mongo.db.users.find_one({"username": profile}) # Find the profile of the user being looked at
    profile_id = user_profile["_id"] # Find the ID of the profile of the user being looked at
    username = user_profile["username"] # Find the username of the ID of the profile being looked at
    remove_friend_profile = mongo.db.users.find_one({"friends": ObjectId(profile_id)})
    friends_of_user = user_profile["friends"] # Find the list of friends of the profile being looked at
    logged_in_user = session["user"] # Name of the logged in user
    logged_in = mongo.db.users.find_one({"username": logged_in_user}) # Profile of the logged in user
    logged_id = logged_in["_id"] # ID of the logged in user
    friends_of_logged_in = logged_in["friends"] # List of friends of the logged in user
    remove_friend_user = mongo.db.users.find_one({"friends": ObjectId(logged_id)})
    # Find the friendship in the collection Friends
    already_friends = mongo.db.friends.find_one({'$or':
    [
        {'$and':[{"is_friends_1": logged_in_user},
        {"is_friends_2": username}]},
        {'$and':[{"is_friends_1": username},
        {"is_friends_2": logged_in_user}]}
    ]})
        
    if request.method == "POST":
        mongo.db.users.find_one_and_update(
            {"_id": profile_id},
            {"$pull": {"friends": remove_friend_profile["_id"]}})
        mongo.db.users.find_one_and_update(
            {"_id": logged_id},
            {"$pull": {"friends": remove_friend_user["_id"]}})
        mongo.db.friends.remove(already_friends)

    flash("Successfully removed friend")      
    return redirect(url_for("profile", username=logged_in_user))




@app.route("/add_friend/<profile>", methods=["GET", "POST"])
def add_friend(profile):
    user_profile = mongo.db.users.find_one({"username": profile})
    username = user_profile["username"]
    logged_in_user = session["user"]
    pending_request = mongo.db.friend_requests.find_one({'$or':
    [
        {'$and':[{"friend_request_from": logged_in_user},
        {"friend_request_to": username}]},
        {'$and':[{"friend_request_from": username},
        {"friend_request_to": logged_in_user}]}        
    ]})
    already_friends = mongo.db.friends.find_one({'$or':
    [
        {'$and':[{"is_friends_1": logged_in_user},
        {"is_friends_2": username}]},
        {'$and':[{"is_friends_1": username},
        {"is_friends_2": logged_in_user}]}
    ]})
    if request.method == "POST":
        #check if the user is already friends or has a friend request pending
        if pending_request:
            flash("Friend request pending")
            return render_template("view_profile.html", profile=username, 
            is_friends=already_friends, pending_request=pending_request)
        if already_friends:
            flash("You're already friends!")
            return render_template("view_profile.html", profile=username, 
            is_friends=already_friends, pending_request=pending_request) 
        #if no friend request pending, then new friend request is posted    
        friend_request = {
            "friend_request_from": session["user"],
            "friend_request_to": username
        }
        mongo.db.friend_requests.insert_one(friend_request)
        flash("Friend request sent")
        return redirect(url_for("view_profile", profile=username, 
            is_friends=already_friends, pending_request=pending_request))
        

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        # check if username already exists in db
        existing_user = mongo.db.users.find_one(
            {"username": request.form.get("username").lower()})
        # check to see if user wants to be permanently logged in on registration
        permanent = request.form.get("remember")
        password = request.form.get("password")
        confirm = request.form.get("confirm")
        if existing_user:
            flash("Username already exists")
            return redirect(url_for("register"))
        if password == confirm:     
            register = {
                "username": request.form.get("username").lower(),
                "password": generate_password_hash(request.form.get("password")),
                "fname": request.form.get("fname"),
                "lname": request.form.get("lname"),
                "bday": request.form.get("bday"),
                "state": request.form.get("state"),
                "country": request.form.get("country"),
                "sex": request.form.get("sex"),
                "friends": []
            }
            mongo.db.users.insert_one(register)

            # put the new user into 'session' cookie
            session["user"] = request.form.get("username").lower()
            session.permanent = permanent
            flash("Registration Successful!")
            return redirect(url_for("profile", username=session["user"]))
    
        else:
            session["non_registered_user"] = request.form.get("username").lower()
            flash("Passwords don't match, try again.")
            
            return render_template("register.html", store_user=session["non_registered_user"])


    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    
    if request.method == "POST":
        # check if username exists in db
        existing_user = mongo.db.users.find_one(
            {"username": request.form.get("username").lower()})
        # see if user wants to be permanently logged in
        permanent = request.form.get("remember")
        if existing_user:
            # ensure hashed password matches user input
            if check_password_hash(
                    existing_user["password"], request.form.get("password")):
                session["user"] = request.form.get("username").lower()
                session.permanent = permanent
                flash("Welcome, {}".format(
                    request.form.get("username")))
                return redirect(url_for(
                    "profile", username=session["user"]))
            else:
                # invalid password match
                flash("Incorrect Username and/or Password")
                return redirect(url_for("login"))

        else:
            # username doesn't exist
            flash("Incorrect Username and/or Password")
            return redirect(url_for("login"))

    return render_template("login.html")
    

@app.route("/profile/<username>", methods=["GET", "POST"])
def profile(username):
    # Get questions that the user has input themselves
    questions = mongo.db.questions.find(
        {"created_by": session["user"]})
    user = session["user"] or None
    # grab the session user's username from db
    username = mongo.db.users.find_one(
        {"username": session["user"]})["username"]
    user_profile = mongo.db.users.find_one({"username": user})
    friend_request = mongo.db.friend_requests.find_one({"friend_request_to": user})
    if session["user"]:
        return render_template("profile.html", username=username, profile=user_profile, 
        friend_request=friend_request, questions=questions)

    return redirect(url_for("login"))


@app.route("/friend_requests/<user>", methods=["GET", "POST"])        
def friend_requests(user):
    user = session["user"]
    logged_in_user = mongo.db.users.find_one({"username": session["user"] })
    logged_in_id = logged_in_user["_id"]
    requested_from = []

    # fetch all requests for current user
    requests = list(mongo.db.friend_requests.find({"friend_request_to": user}))

    # project list of requestors profiles 
    requests_from = list(map(lambda x: x['friend_request_from'], requests))

    # fetch all requestors profiles
    profiles = mongo.db.users.find({"username": {"$in":requests_from}})

    # transform list of requestors profiles into dict
    requestors = {profile['username']: profile for profile in profiles}
    
    if request.method == "POST":
        accept_friend = request.form.get("accept")
        decline_friend = request.form.get("decline")
        
        if accept_friend:
            requestors_user = mongo.db.users.find_one({"username": accept_friend})
            requestors_id = requestors_user["_id"]
            friendship = {
                "is_friends_1": accept_friend,
                "is_friends_2": user
            }
            request_accepted = {
                "friend_request_from": accept_friend,
                "friend_request_to": user
            }
            mongo.db.friend_requests.delete_one(request_accepted)
            mongo.db.friends.insert_one(friendship)
            mongo.db.users.find_one_and_update({"_id": logged_in_id},
                {"$push": {"friends": requestors_id}})
            mongo.db.users.find_one_and_update({"_id": requestors_id},
                {"$push": {"friends": logged_in_id}})
            flash("Friend request accepted")
            
            return redirect(url_for("friend_requests", requests=requests, requestors=requestors, user=session["user"]))
            
        else:
            request_declined = {
                "friend_request_from": decline_friend,
                "friend_request_to": user
            }
            mongo.db.friend_requests.delete_one(request_declined)
            flash("Friend request declined")
            return redirect(url_for("friend_requests", requests=requests, requestors=requestors, user=session["user"]))

    return render_template("friend_requests.html", requests=requests, requestors=requestors)


@app.route("/add_question", methods=["GET", "POST"])
def add_question():
    if request.method == "POST":
        is_friends = "on" if request.form.get("is_friends") else "off"
        question = {
            "question_title": request.form.get("question_title"),
            "question_text": request.form.get("question_text"),
            "is_friends": is_friends,
            "created_by": session["user"],
            "added_on": datetime.now().strftime("%d %b %Y %H:%M.%S"),
        }

        mongo.db.questions.insert_one(question)
        flash("Question Successfully Added")
        return redirect(url_for("get_questions"))

    return render_template("add_question.html")


@app.route("/edit_question/<question_id>", methods=["GET", "POST"])
def edit_question(question_id):
    user = session["user"] or None
    created_byId = mongo.db.questions.find_one({"_id" : ObjectId(question_id)})
    created_by = created_byId["created_by"]
    if user == created_by or "9dyhnxe8u4":
        if request.method == "POST":
            is_friends = "on" if request.form.get("is_friends") else "off"
            submit = {
                "$set": {
                    "question_title": request.form.get("question_title"),
                    "question_text": request.form.get("question_text"),
                    "is_friends": is_friends,
                    "edited_on": datetime.now().strftime("%d %b %Y %H:%M.%S")
                    }
            }    

            mongo.db.questions.update_one({"_id": ObjectId(question_id)}, submit)
            flash("Question Successfully Edited")
    else:
        return redirect(url_for("get_questions"))
    
    question = mongo.db.questions.find_one({"_id": ObjectId(question_id)})
    return render_template("edit_question.html", question=question)


@app.route("/cons/<question_id>", methods=["GET", "POST"])
def cons(question_id):
    user = session["user"] or None
    questions = list(mongo.db.questions.find().sort("added_on", -1))
    if request.method == "POST":
        con = {
                "con": request.form.get("con"),
                "user": user 
            }

        mongo.db.questions.update_one({"_id": ObjectId(question_id)},{"$push":{"cons": con}})
        flash("Successfully Added a Con")

    return render_template("questions.html", questions=questions )


@app.route("/pros/<question_id>", methods=["GET", "POST"])
def pros(question_id):
    user = session["user"] or None
    questions = list(mongo.db.questions.find().sort("added_on", -1))
    
    if request.method == "POST":
        pro = {
                "pro": request.form.get("pro"),
                "user": user 
            }
       
        mongo.db.questions.update_one({"_id": ObjectId(question_id)},{"$push":{"pros": pro}})
        flash("Successfully Added a Pro")

    return render_template("questions.html", questions=questions )


@app.route("/edit_profile/", methods=["GET", "POST"])
def edit_profile():
    with open('countries.json', encoding="utf8") as f:
               country = json.load(f)

    user = session["user"] or None
    if user: 
        user_profile = mongo.db.users.find_one({"username": user})
        users_id = user_profile["_id"]

        if request.method == "POST":
            sex = request.form['sex']
            submit = {
                "$set": {
                    "fname": request.form.get("fname"),
                    "lname": request.form.get("lname"),
                    "sex": sex,
                    "state": request.form.get("state"),
                    "country": request.form.get("country"),
                    "bday": request.form.get("bday")
                }
            }

            mongo.db.users.update_one({"_id": ObjectId(users_id)}, submit)
            flash("Profile Successfully Edited")
            user_profile = mongo.db.users.find_one({"_id": ObjectId(users_id)})
            return render_template("edit_profile.html", profile=user_profile, countries=country)
    
        else:
            return render_template("edit_profile.html", profile=user_profile, countries=country)
        
    return redirect(url_for("login"))


@app.route("/delete_question/<question_id>", methods=["GET", "POST"])
def delete_question(question_id):
    user = session["user"] or None
    created_byId = mongo.db.questions.find_one({"_id" : ObjectId(question_id)})
    created_by = created_byId["created_by"]
    if user == created_by or "9dyhnxe8u4":
        if request.method == "POST":
            mongo.db.questions.delete_one({"_id": ObjectId(question_id)})
            flash("Question Successfully Deleted")
    else:
        return redirect(url_for("get_questions"))
        
    return redirect(url_for("get_questions"))


@app.route("/logout")
def logout():
    # remove user from session cookie
    flash("You have been logged out")
    session.pop("user")
    return redirect(url_for("login"))


if __name__ == "__main__":
    app.run(host=os.environ.get("IP"),
    port=int(os.environ.get("PORT")),
    debug=True)
