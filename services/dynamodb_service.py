import os
import boto3
from dotenv import load_dotenv
from decimal import Decimal
from datetime import date, datetime, timedelta

load_dotenv()

dynamodb = boto3.resource(
    'dynamodb',
    region_name=os.getenv("AWS_REGION"),
    aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
    aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY")
)

users_table = dynamodb.Table(os.getenv("DYNAMODB_USERS_TABLE"))


#  CREATE USER
def create_user(user_id, username, password):
    return users_table.put_item(
        Item={
            "user_id": user_id,
            "username": username,
            "password": password
        }
    )

#  GET USER
def get_user(username):

    response = users_table.scan()

    for user in response.get("Items", []):

        if user.get("username") == username:
            return user

    return None


#  UPDATE USER PROGRESS (basic starter)
def update_user_progress(user_id, progress):
    return users_table.update_item(
        Key={"user_id": user_id},
        UpdateExpression="SET progress = :p",
        ExpressionAttributeValues={
            ":p": progress
        }
    )

quiz_table = dynamodb.Table(os.getenv("DYNAMODB_QUIZ_TABLE"))
users_table = dynamodb.Table(os.getenv("DYNAMODB_USERS_TABLE"))

def save_quiz(quiz_id, user_id, topic, quiz_content):

    return quiz_table.put_item(
        Item={
            "quiz_id": quiz_id,
            "user_id": user_id,
            "topic": topic,
            "quiz_content": quiz_content
        }
    )


def get_user_quizzes(user_id):

    response = quiz_table.scan()

    quizzes = []

    for item in response.get("Items", []):

        # Skip old records without user_id
        if "user_id" not in item:
            continue

        if item["user_id"] == user_id:
            quizzes.append(item)

    return quizzes

progress_table = dynamodb.Table(os.getenv("DYNAMODB_PROGRESS_TABLE"))
def init_progress(user_id):

    return progress_table.put_item(
        Item={
            "user_id": user_id,
            "xp": 0,
            "streak": 0,
            "quizzes_taken": 0,
            "level": 1,
            "last_login_date": str(date.today())
        }
    )


def update_xp(user_id, xp_gain):

    response = progress_table.get_item(
        Key={"user_id": user_id}
    )

    user = response["Item"]

    xp = int(user["xp"]) + xp_gain
    new_level = (xp // 50) + 1

    return progress_table.update_item(
        Key={"user_id": user_id},

        UpdateExpression="SET xp = :x, #lvl = :l",

        ExpressionAttributeNames={
            "#lvl": "level"
        },

        ExpressionAttributeValues={
            ":x": xp,
            ":l": new_level
        }
    )


def get_progress(user_id):

    response = progress_table.get_item(
        Key={"user_id": user_id}
    )

    item = response.get("Item")

    if item:
        for key, value in item.items():
            if isinstance(value, Decimal):
                item[key] = int(value)

    return item

def update_quiz_count(user_id):

    return progress_table.update_item(
        Key={"user_id": user_id},
        UpdateExpression="SET quizzes_taken = quizzes_taken + :q",
        ExpressionAttributeValues={
            ":q": 1
        }
    )

def update_login_streak(user_id):

    progress = get_progress(user_id)

    if not progress:
        return

    today = date.today()
    last_login = datetime.strptime(
        progress["last_login_date"],
        "%Y-%m-%d"
    ).date()

    current_streak = progress["streak"]

    # User logged in on consecutive day
    if today == last_login + timedelta(days=1):

        new_streak = current_streak + 1

    # User already logged in today
    elif today == last_login:

        return

    # User broke streak
    else:

        new_streak = 1

    progress_table.update_item(
        Key={"user_id": user_id},
        UpdateExpression="""
            SET streak = :s,
                last_login_date = :d
        """,
        ExpressionAttributeValues={
            ":s": new_streak,
            ":d": str(today)
        }
    )