# Ejemplo: conectar tu app Python al ecosistema Antigravity
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "sdk"))
from client import Client

client = Client()
print(client.health())
print(client.list_agents())
