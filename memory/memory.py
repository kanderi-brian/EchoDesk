import json
import os
from core.app_paths import data_root
from datetime import datetime


class Memory:

    def __init__(self):

        root = data_root(); root.mkdir(parents=True, exist_ok=True)
        self.file = str(root / "memory.json")

        if not os.path.exists(self.file):
            self.create_memory()


    def create_memory(self):

        data = {
            "history": []
        }

        with open(self.file, "w") as file:
            json.dump(data, file, indent=4)


    def remember(self, user, response):

        with open(self.file, "r") as file:
            data = json.load(file)


        data["history"].append(
            {
                "time": str(datetime.now()),
                "user": user,
                "EchoDesk": response,
            }
        )


        with open(self.file, "w") as file:
            json.dump(data, file, indent=4)

        try:
            from context.context import get_context_engine

            context_engine = get_context_engine()
            context_engine.add_assistant_message(response)
        except Exception:
            pass



    def recall(self):

        with open(self.file, "r") as file:
            data = json.load(file)

        return data["history"]
