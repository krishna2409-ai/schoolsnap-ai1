import requests

url = "http://localhost:8000/load-event-folder"
data = {
    "folder_path": r"F:\Bindu's Wedding\Edited\Wedding",
    "event_name": "Bindu Wedding"
}

try:
    response = requests.post(url, data=data)
    print("Status Code:", response.status_code)
    print("Response:", response.json())
except Exception as e:
    print("Error:", e)
