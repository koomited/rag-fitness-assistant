import os
import requests
from tqdm.auto import tqdm
import json
from db import init_db



if __name__ == "__main__":
    print("[INFO] Initializing PostgreSQL database...")
    init_db()