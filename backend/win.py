import os
import tkinter as tk
from tkinter import filedialog, messagebox
import requests

class FileUploaderApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Загрузка файлов")
        self.root.geometry("600x400")

        self.selected_files = []

        # Метки и кнопки
        self.label = tk.Label(root, text="Выберите папку для загрузки файлов:")
        self.label.pack(pady=10)

        self.select_button = tk.Button(root, text="Выбрать папку", command=self.select_folder)
        self.select_button.pack(pady=5)

        # Список файлов
        self.file_listbox = tk.Listbox(root, width=80, height=15)
        self.file_listbox.pack(pady=10)

        # Кнопка загрузки
        self.upload_button = tk.Button(root, text="Загрузить файлы", command=self.upload_files, state=tk.DISABLED)
        self.upload_button.pack(pady=5)

        # Метка статуса
        self.status_label = tk.Label(root, text="", fg="blue")
        self.status_label.pack(pady=5)

    def select_folder(self):
        # Выбор папки
        folder_path = filedialog.askdirectory()
        if folder_path:
            self.selected_files = []
            # Рекурсивно собираем файлы из папки
            for root, _, files in os.walk(folder_path):
                for file in files:
                    if file.lower().endswith(('.jpg', '.jpeg', '.png')):
                        self.selected_files.append(os.path.join(root, file))
            self.update_file_listbox()

    def update_file_listbox(self):
        # Обновление списка файлов
        self.file_listbox.delete(0, tk.END)
        if self.selected_files:
            for file in self.selected_files:
                self.file_listbox.insert(tk.END, file)
            self.upload_button.config(state=tk.NORMAL)
        else:
            self.file_listbox.insert(tk.END, "Нет подходящих файлов для загрузки.")
            self.upload_button.config(state=tk.DISABLED)

    def upload_files(self):
        if not self.selected_files:
            messagebox.showwarning("Внимание", "Сначала выберите файлы для загрузки.")
            return

        self.status_label.config(text="Загрузка началась...")
        successful_uploads = 0

        for file_path in self.selected_files:
            try:
                with open(file_path, 'rb') as file_obj:
                    response = requests.post(
                        "http://localhost:5000/upload",
                        files={'files': file_obj},
                        data={'tags': 'example_tag'}
                    )
                    if response.status_code == 200:
                        successful_uploads += 1
                    else:
                        print(f"Неудачный ответ сервера: {response.text}")
            except Exception as e:
                print(f"Ошибка загрузки файла {file_path}: {str(e)}")

        self.status_label.config(text=f"Загрузка завершена. Успешно загружено: {successful_uploads} из {len(self.selected_files)}.")

if __name__ == "__main__":
    root = tk.Tk()
    app = FileUploaderApp(root)
    root.mainloop()