# server/services/task_service.py
import os
import json
import time
import config  # [NEW] Импортируем конфигурацию для доступа к .env

class TaskService:
    def __init__(self, tasks_dir=None):
        # [UPDATED] Если tasks_dir не передан явно, берем путь из конфигурации (.env)
        self.tasks_dir = tasks_dir or getattr(config, "TASKS_FOLDER", "data/tasks")
        
        if not os.path.exists(self.tasks_dir):
            try:
                os.makedirs(self.tasks_dir, exist_ok=True)
            except OSError:
                pass

    def save_state(self, task_id, state):
        """Сохраняет состояние задачи атомарно"""
        try:
            filepath = os.path.join(self.tasks_dir, f"{task_id}.json")
            temp_filepath = filepath + ".tmp"
            with open(temp_filepath, 'w') as f:
                json.dump(state, f)
            os.replace(temp_filepath, filepath)
        except Exception as e:
            print(f"Error saving task {task_id}: {e}")

    def get_state(self, task_id):
        """Читает состояние задачи"""
        filepath = os.path.join(self.tasks_dir, f"{task_id}.json")
        if not os.path.exists(filepath):
            return None
        try:
            with open(filepath, 'r') as f:
                return json.load(f)
        except Exception:
            return None