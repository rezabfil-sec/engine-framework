#!/usr/bin/python3

import time
import json
import jwt
import requests

# load the credentials from the JSON file
service_account_file = 'service_account_file.json'
json_filename = '../GCP_tools/' + service_account_file
with open(json_filename, 'r') as f:
    data = f.read()
json_credentials = json.loads(data)

# get the private key from the credentials
private_key = json_credentials['private_key']

# create the JWT
time_issued = int(time.time())
expires = time_issued + 3600

# create JWT headers
jwt_headers = {
    'kid': json_credentials['private_key_id'],
    'alg': 'RS256',
    'typ': 'JWT'
}
# create JWT payload
jwt_payload = {
    'iss': json_credentials['client_email'],
    'sub': json_credentials['client_email'],
    'aud': 'https://www.googleapis.com/oauth2/v4/token',
    'iat': time_issued,
    'exp': expires,
    'scope': 'https://www.googleapis.com/auth/cloud-platform'
}

# create the signed JWT
signed_jwt = jwt.encode(jwt_payload, private_key, algorithm='RS256', headers=jwt_headers)

# get the access token
oauth_endpoint = 'https://www.googleapis.com/oauth2/v4/token'
response = requests.post(oauth_endpoint, data={'grant_type': 'urn:ietf:params:oauth:grant-type:jwt-bearer', 'assertion': signed_jwt})

if response.ok:
    print((response.json()['access_token']).strip())
else:
    print(response.text)

