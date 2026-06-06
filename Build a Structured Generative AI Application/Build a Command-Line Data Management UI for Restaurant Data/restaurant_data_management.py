from ibm_watsonx_ai import Credentials
from ibm_watsonx_ai.foundation_models import ModelInference
import json
import os
import shutil
import io
import unittest
from unittest.mock import patch


FILEPATH = "structured_restaurant_data.json"
BACKUP_PATH = "structured_restaurant_data.json.bak"


# -----------------------------
# FILE HELPERS (MISSING FIX)
# -----------------------------
def load_data(file_path):
    if not os.path.exists(file_path):
        return []
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_data(data, file_path, backup_path):
    # backup
    if os.path.exists(file_path):
        shutil.copy(file_path, backup_path)

    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)


def show_restaurant_card(res, index):
    print(f"\n--- Restaurant {index} ---")
    for k, v in res.items():
        print(f"{k}: {v}")


# -----------------------------
# LLM PROMPT
# -----------------------------
def restaurant_data_structure_prompt_generation(restaurant_paragraph):

    system_msg = """
    You are an expert data extraction assistant.

    Extract restaurant info and return ONLY valid JSON.

    Fields:
    name, location, type, food_style, rating,
    price_range, signatures, vibe, environment, shortcomings

    Rules:
    - Return ONLY JSON
    - price_range = number of '$'
    - signatures = list
    - shortcomings = list (empty if missing)
    """

    prompt_txt = f"""
    Convert this restaurant description into JSON:

    {restaurant_paragraph}
    """

    return system_msg, prompt_txt


# -----------------------------
# LLM FUNCTION
# -----------------------------
def llm_model(system_msg, prompt_txt, params=None):

    model_id = "ibm/granite-4-h-small"
    project_id = "skills-network"

    credentials = Credentials(url="https://us-south.ml.cloud.ibm.com")

    model = ModelInference(
        model_id=model_id,
        credentials=credentials,
        project_id=project_id,
        params=params or {"max_new_tokens": 512, "temperature": 0.1},
    )

    messages = [
        {"role": "system", "content": system_msg},
        {"role": "user", "content": prompt_txt},
    ]

    response = model.chat(messages=messages)
    return response["choices"][0]["message"]["content"]


# -----------------------------
# JSON REPAIR
# -----------------------------
def JSON_auto_repair_prompts(response, error_message):

    system_msg = "Fix JSON only. Return ONLY valid JSON."

    prompt = f"""
Candidate:
{response}

Error:
{error_message}

Fix it.
"""

    return system_msg, prompt


# -----------------------------
# NEW ENTRY PROCESS
# -----------------------------
def new_data_entry_process(paragraph, itemId):

    system_msg, prompt_txt = restaurant_data_structure_prompt_generation(paragraph)

    response = llm_model(system_msg, prompt_txt)

    try:
        data = json.loads(response)
    except Exception as e:
        repair_sys, repair_prompt = JSON_auto_repair_prompts(response, str(e))
        fixed = llm_model(repair_sys, repair_prompt)
        data = json.loads(fixed)

    data["itemId"] = itemId
    return data


# -----------------------------
# MAIN UI
# -----------------------------
def manage_restaurants(file_path, backup_path):

    while True:
        data = load_data(file_path)

        print(f"\n🏨 DATABASE | Records: {len(data)}")
        print("1. Browse Names")
        print("2. View Record")
        print("3. Add")
        print("4. Edit")
        print("5. Delete")
        print("6. Exit")

        choice = input("Action: ")

        if choice == "1":
            for i, r in enumerate(data):
                print(f"{i}: {r.get('name', 'N/A')}")

        elif choice == "2":
            try:
                idx = int(input("Index: "))
                if 0 <= idx < len(data):
                    show_restaurant_card(data[idx], idx)
                else:
                    print("invalid index")
            except:
                print("invalid index")

        elif choice in ["3", "4", "5"]:
            print("\nSECURITY CHECK")
            if input("type yes: ") != "yes":
                print("Operation cancelled.")
                continue

            if choice == "3":
                itemId = 1000000 + len(data) + 1
                paragraph = input("Enter description: ")

                new_item = new_data_entry_process(paragraph, itemId)
                data.append(new_item)

                save_data(data, file_path, backup_path)
                print("✅ Restaurant added.")

            elif choice == "4":
                try:
                    idx = int(input("Index: "))
                    if 0 <= idx < len(data):
                        for k in data[idx]:
                            v = input(f"{k} ({data[idx][k]}): ")
                            if v.strip():
                                data[idx][k] = v
                        save_data(data, file_path, backup_path)
                        print("✅ Record updated.")
                    else:
                        print("invalid index")
                except:
                    print("invalid index")

            elif choice == "5":
                try:
                    idx = int(input("Index: "))
                    if 0 <= idx < len(data):
                        data.pop(idx)
                        save_data(data, file_path, backup_path)
                        print("✅ Restaurant deleted.")
                    else:
                        print("invalid index")
                except:
                    print("invalid index")

        elif choice == "6":
            break

        else:
            print("Invalid input")


# -----------------------------
# UNIT TESTS (FIXED INDENT)
# -----------------------------
class TestRestaurantDatabase(unittest.TestCase):
    def setUp(self):
        self.test_file = "structured_restaurant_data_unit_test.json"
        self.test_file_backup = "structured_restaurant_data_unit_test.json.bak"
        self.initial_data = [{"name": "Test Cafe", "location": "Test City"}]

        with open(self.test_file, "w") as f:
            json.dump(self.initial_data, f)

    def tearDown(self):
        if os.path.exists(self.test_file):
            os.remove(self.test_file)
        if os.path.exists(self.test_file_backup):
            os.remove(self.test_file_backup)

    @patch("builtins.input")
    @patch("sys.stdout", new_callable=io.StringIO)
    def test_add_and_delete_restaurant_success(self, mock_stdout, mock_input):

        mock_restaurant = "A cozy modern cafe with artisan food and drinks."

        mock_input.side_effect = ["3", "yes", mock_restaurant, "6"]

        try:
            manage_restaurants(self.test_file, self.test_file_backup)
        except:
            pass

        with open(self.test_file) as f:
            data = json.load(f)

        self.assertEqual(len(data), 2)
        self.assertIn("Restaurant added", mock_stdout.getvalue())

    @patch("builtins.input")
    @patch("sys.stdout", new_callable=io.StringIO)
    def test_delete_security_cancel(self, mock_stdout, mock_input):

        mock_input.side_effect = ["5", "no", "6"]

        manage_restaurants(self.test_file, self.test_file_backup)

        with open(self.test_file) as f:
            data = json.load(f)

        self.assertEqual(len(data), 1)
        self.assertIn("Operation cancelled", mock_stdout.getvalue())


# -----------------------------
# RUN
# -----------------------------
if __name__ == "__main__":
    unittest.main()
