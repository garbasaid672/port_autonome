import smtplib
import json
from email.message import EmailMessage


json_file = open("gmail_config.json")
gmail_confg = json.load(json_file)

print(gmail_confg)

msg= EmailMessage()
msg["to"]="garbamohamedseildoul@gmail.com"
msg["from"]="garbamohamedseildoul@gmail.com"
msg["Subject"]= "Send email avec python"
msg.set_content("Hi !! this is my first message with python")

with smtplib.SMTP_SSL(gmail_confg["server"],gmail_confg["port"]) as smtp:
     smtp.login(gmail_confg["email"],gmail_confg["password"])
     smtp.send_message(msg)
     print("Email sent !")
