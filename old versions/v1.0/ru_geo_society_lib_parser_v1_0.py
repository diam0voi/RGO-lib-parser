import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import requests
import base64
import os
import re
import time
import threading
from PIL import Image

'''Глобальные настройки (смело редактируется)'''
DEFAULT_SPREAD_BG_COLOR = (255, 255, 255)
DEFAULT_SPREAD_ASPECT_RATIO_THRESHOLD = 1.1
DEFAULT_DELAY_SECONDS = 0.5
DEFAULT_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/100.0.0.0 Safari/537.36"


def get_page_number(filename):
    match = re.search(r'\d+', filename)
    return int(match.group()) if match else -1


def is_likely_spread(image_path, threshold):
    try:
        with Image.open(image_path) as img:
            width, height = img.size
            if height == 0: return False
            aspect_ratio = width / height
            return aspect_ratio > threshold
    except Exception:
        return False



class JournalDownloaderApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Загрузчик + склейщик файлов из библиотеки РГО. v1.0 by b0s")
        self.root.minsize(550, 600) 

        style = ttk.Style()
        style.configure("TLabel", padding=5)
        style.configure("TButton", padding=5)
        style.configure("TEntry", padding=5)

        input_frame = ttk.LabelFrame(root, text="Параметры Загрузки", padding=10)
        input_frame.pack(padx=10, pady=10, fill=tk.X)

        ''' Поля ввода '''
        # URL base
        ttk.Label(input_frame, text="Базовый URL (до ID):").grid(row=0, column=0, sticky=tk.W)
        self.url_base_entry = ttk.Entry(input_frame, width=50)
        self.url_base_entry.grid(row=0, column=1, sticky=tk.EW)
        self.url_base_entry.insert(0, "https://elib.rgo.ru/safe-view/")

        # URL IDs
        ttk.Label(input_frame, text="ID конкретного файла (через /):").grid(row=1, column=0, sticky=tk.W)
        self.url_ids_entry = ttk.Entry(input_frame, width=50)
        self.url_ids_entry.grid(row=1, column=1, sticky=tk.EW)
        self.url_ids_entry.insert(0, "123456789/217168/1/")  # Пример

        # PDF Filename
        ttk.Label(input_frame, text="Имя файла на сайте:").grid(row=2, column=0, sticky=tk.W)
        self.pdf_filename_entry = ttk.Entry(input_frame, width=50)
        self.pdf_filename_entry.grid(row=2, column=1, sticky=tk.EW)
        self.pdf_filename_entry.insert(0, "002_R.pdf")  # Пример

        # Total Pages
        ttk.Label(input_frame, text="Кол-во страниц файла:").grid(row=3, column=0, sticky=tk.W)
        self.total_pages_entry = ttk.Entry(input_frame, width=10)
        self.total_pages_entry.grid(row=3, column=1, sticky=tk.W)
        self.total_pages_entry.insert(0, "56")  # Пример

        # Cookies
        ttk.Label(input_frame, text="Ваши Cookies (из DevTools):").grid(row=4, column=0, sticky=tk.W)
        self.cookies_entry = tk.Text(input_frame, height=4, width=50)
        self.cookies_entry.grid(row=4, column=1, sticky=tk.EW)
        self.cookies_entry.insert(tk.END, "JSESSIONID=...; ym_uid=...; ym_d=...; ym_isad=...")  # Пример

        # Папка для страниц
        ttk.Label(input_frame, text="Папка для скачанных страниц:").grid(row=5, column=0, sticky=tk.W)
        self.pages_dir_entry = ttk.Entry(input_frame, width=40)
        self.pages_dir_entry.grid(row=5, column=1, sticky=tk.EW)
        self.pages_dir_entry.insert(0, "downloaded_pages")
        self.browse_pages_button = ttk.Button(input_frame, text="Обзор...", command=self.browse_output_pages)
        self.browse_pages_button.grid(row=5, column=2, padx=5)

        # Папка для разворотов
        ttk.Label(input_frame, text="Папка для готовых разворотов:").grid(row=6, column=0, sticky=tk.W)
        self.spreads_dir_entry = ttk.Entry(input_frame, width=40)
        self.spreads_dir_entry.grid(row=6, column=1, sticky=tk.EW)
        self.spreads_dir_entry.insert(0, "final_spreads")
        self.browse_spreads_button = ttk.Button(input_frame, text="Обзор...", command=self.browse_output_spreads)
        self.browse_spreads_button.grid(row=6, column=2, padx=5)

        # Растягиваем колонку с полями ввода
        input_frame.columnconfigure(1, weight=1)

        # Для кнопок управления
        control_frame = ttk.Frame(root, padding=10)
        control_frame.pack(fill=tk.X)

        self.run_all_button = ttk.Button(control_frame, text="Скачать и создать развороты", command=self.run_all)
        self.run_all_button.pack(side=tk.LEFT, padx=5)

        self.download_button = ttk.Button(control_frame, text="Только скачать страницы", command=self.run_download)
        self.download_button.pack(side=tk.LEFT, padx=5)

        self.process_button = ttk.Button(control_frame, text="Только создать развороты", command=self.run_processing)
        self.process_button.pack(side=tk.LEFT, padx=5)

        # Для области лога
        status_frame = ttk.LabelFrame(root, text="Статус", padding=10)
        status_frame.pack(padx=10, pady=10, fill=tk.BOTH, expand=True)

        self.status_text = scrolledtext.ScrolledText(status_frame, height=15, wrap=tk.WORD, state=tk.DISABLED)
        self.status_text.pack(fill=tk.BOTH, expand=True)

    # Для кнопок Обзор
    def browse_output_pages(self):
        directory = filedialog.askdirectory()
        if directory:
            self.pages_dir_entry.delete(0, tk.END)
            self.pages_dir_entry.insert(0, directory)

    def browse_output_spreads(self):
        directory = filedialog.askdirectory()
        if directory:
            self.spreads_dir_entry.delete(0, tk.END)
            self.spreads_dir_entry.insert(0, directory)

    # Для обновления лога (потокобезопасно)
    def update_status(self, message):
        self.status_text.config(state=tk.NORMAL)
        self.status_text.insert(tk.END, message + "\n")
        self.status_text.see(tk.END)
        self.status_text.config(state=tk.DISABLED)
        self.root.update_idletasks()

    def clear_status(self):
        self.status_text.config(state=tk.NORMAL)
        self.status_text.delete(1.0, tk.END)
        self.status_text.config(state=tk.DISABLED)

    # Для разделения процессов по потокам
    def run_download(self):
        if not self._validate_download_inputs():
            return
        self.clear_status()
        self._set_buttons_state(tk.DISABLED)
        thread = threading.Thread(target=self._thread_download, daemon=True)
        thread.start()

    def run_processing(self):
        if not self._validate_processing_inputs():
            return
        self.clear_status()
        self._set_buttons_state(tk.DISABLED)
        thread = threading.Thread(target=self._thread_process, daemon=True)
        thread.start()

    def run_all(self):
        if not self._validate_download_inputs() or not self._validate_processing_inputs():
            return
        self.clear_status()
        self._set_buttons_state(tk.DISABLED)
        thread = threading.Thread(target=self._thread_run_all, daemon=True)
        thread.start()

    def _set_buttons_state(self, state):
        self.download_button.config(state=state)
        self.process_button.config(state=state)
        self.run_all_button.config(state=state)
        self.browse_pages_button.config(state=state)
        self.browse_spreads_button.config(state=state)

    def _validate_download_inputs(self):
        if not self.url_base_entry.get() or not self.url_ids_entry.get() or \
           not self.pdf_filename_entry.get() or not self.total_pages_entry.get() or \
           not self.cookies_entry.get("1.0", tk.END).strip() or not self.pages_dir_entry.get():
            messagebox.showerror("Ошибка ввода", "Пожалуйста, заполните все поля для загрузки.")
            return False
        try:
            int(self.total_pages_entry.get())
        except ValueError:
            messagebox.showerror("Ошибка ввода", "Количество страниц должно быть числом.")
            return False
        return True

    def _validate_processing_inputs(self):
        if not self.pages_dir_entry.get() or not self.spreads_dir_entry.get():
             messagebox.showerror("Ошибка ввода", "Пожалуйста, укажите папки для страниц и разворотов.")
             return False
        if not os.path.isdir(self.pages_dir_entry.get()):
             messagebox.showerror("Ошибка папки", f"Папка со страницами '{self.pages_dir_entry.get()}' не найдена.")
             return False
        return True

    def _thread_download(self):
        try:
            base_url = self.url_base_entry.get().strip().rstrip('/') + '/'
            url_ids = self.url_ids_entry.get().strip().rstrip('/') + '/'
            filename_pdf = self.pdf_filename_entry.get().strip()
            total_pages = int(self.total_pages_entry.get())
            cookie_string = self.cookies_entry.get("1.0", tk.END).strip()
            output_dir = self.pages_dir_entry.get().strip()

            cookies = {}
            if cookie_string:
                 cookies = {c.split('=')[0].strip(): c.split('=')[1].strip() for c in cookie_string.split(';') if '=' in c}

            headers = {'User-Agent': DEFAULT_USER_AGENT}
            os.makedirs(output_dir, exist_ok=True)

            self.root.after(0, lambda: self.update_status(f"Начинаем скачивание {total_pages} страниц в '{output_dir}'..."))

            session = requests.Session()
            session.headers.update(headers)
            session.cookies.update(cookies)

            success_count = 0
            for i in range(total_pages):
                page_string = f"{filename_pdf}/{i}"
                page_b64_bytes = base64.b64encode(page_string.encode('utf-8'))
                page_b64_string = page_b64_bytes.decode('utf-8')

                final_url = base_url + url_ids + page_b64_string
                output_filename = os.path.join(output_dir, f"page_{i:03d}.jpg")

                status_msg = f"Скачиваю страницу {i+1}/{total_pages} -> {os.path.basename(output_filename)}"
                self.root.after(0, lambda msg=status_msg: self.update_status(msg))

                try:
                    response = session.get(final_url, timeout=30)
                    response.raise_for_status()

                    # Пытаемся определить реальное расширение
                    content_type = response.headers.get('Content-Type', '').lower()
                    extension = ".jpg"
                    if 'png' in content_type: extension = ".png"
                    elif 'gif' in content_type: extension = ".gif"
                    elif 'bmp' in content_type: extension = ".bmp"
                    elif 'tiff' in content_type: extension = ".tiff"
                    if extension != ".jpg":
                        final_output_filename = os.path.join(output_dir, f"page_{i:03d}{extension}")
                    else:
                        final_output_filename = output_filename

                    with open(final_output_filename, 'wb') as f:
                        f.write(response.content)

                    if os.path.getsize(final_output_filename) == 0:
                        self.root.after(0, lambda name=final_output_filename: self.update_status(f"Предупреждение: Файл {os.path.basename(name)} пустой."))
                    else:
                         success_count += 1

                except requests.exceptions.RequestException as e:
                    error_msg = f"Ошибка при скачивании страницы {i}: {e}"
                    self.root.after(0, lambda msg=error_msg: self.update_status(msg))
                except Exception as e:
                    error_msg = f"Неожиданная ошибка на странице {i}: {e}"
                    self.root.after(0, lambda msg=error_msg: self.update_status(msg))

                time.sleep(DEFAULT_DELAY_SECONDS)

            final_msg = f"Скачивание завершено. Успешно скачано {success_count} из {total_pages} страниц."
            self.root.after(0, lambda msg=final_msg: self.update_status(msg))
            if success_count == total_pages:
                 self.root.after(0, lambda: messagebox.showinfo("Успех", "Все страницы успешно скачаны!"))
            else:
                 self.root.after(0, lambda: messagebox.showwarning("Завершено с ошибками", f"Скачано {success_count} из {total_pages} страниц. Проверьте лог статуса."))

        except Exception as e:
            error_msg = f"Критическая ошибка при скачивании: {e}"
            self.root.after(0, lambda msg=error_msg: self.update_status(msg))
            self.root.after(0, lambda: messagebox.showerror("Ошибка", f"Произошла критическая ошибка:\n{e}"))
        finally:
            self.root.after(0, lambda: self._set_buttons_state(tk.NORMAL))  # В основном потоке

    def _thread_process(self):
        try:
            input_folder = self.pages_dir_entry.get().strip()
            output_folder = self.spreads_dir_entry.get().strip()
            image_extensions = ('.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff')  # Других не попадалось

            self.root.after(0, lambda: self.update_status(f"Начинаем обработку изображений из '{input_folder}' в '{output_folder}'..."))

            os.makedirs(output_folder, exist_ok=True)

            try:
                all_files = [f for f in os.listdir(input_folder) if f.lower().endswith(image_extensions)]
            except FileNotFoundError:
                self.root.after(0, lambda: self.update_status(f"Ошибка: Папка '{input_folder}' не найдена."))
                self.root.after(0, lambda: messagebox.showerror("Ошибка", f"Папка '{input_folder}' не найдена."))
                return

            sorted_files = sorted([f for f in all_files if get_page_number(f) != -1], key=get_page_number)

            if not sorted_files:
                self.root.after(0, lambda: self.update_status("В папке не найдено подходящих файлов изображений с номерами."))
                self.root.after(0, lambda: messagebox.showwarning("Нет файлов", "Не найдено файлов для обработки в указанной папке."))
                return

            self.root.after(0, lambda: self.update_status(f"Найдено {len(sorted_files)} файлов. Создание разворотов..."))

            page_index = 0
            processed_count = 0
            while page_index < len(sorted_files):
                current_file = sorted_files[page_index]
                current_path = os.path.join(input_folder, current_file)
                current_page_num = get_page_number(current_file)
                current_is_spread = page_index > 0 and is_likely_spread(current_path, DEFAULT_SPREAD_ASPECT_RATIO_THRESHOLD)

                # Вариант 1: Текущий файл - разворот или вечно одинокая обложка
                if current_is_spread or page_index == 0:
                    _, ext = os.path.splitext(current_file)  # Гадаем с расширением
                    output_filename = f"spread_{current_page_num:03d}{ext}"
                    output_path = os.path.join(output_folder, output_filename)
                    status_msg = f"Копирую {'обложку' if page_index == 0 else 'готовый разворот'}: {current_file} -> {output_filename}"
                    self.root.after(0, lambda msg=status_msg: self.update_status(msg))
                    try:
                        img = Image.open(current_path)
                        if img.format in ['JPEG', 'PNG', 'BMP', 'GIF', 'TIFF']:
                             if img.mode == 'RGBA' and img.format in ['PNG', 'GIF']:
                                 img.save(output_path)  # Для прозрачности
                             else:
                                 img.convert('RGB').save(output_path)
                        else:
                             img.convert('RGB').save(output_path, "PNG")
                        img.close()
                        processed_count += 1
                    except Exception as e:
                        error_msg = f"Ошибка при копировании {current_file}: {e}"
                        self.root.after(0, lambda msg=error_msg: self.update_status(msg))
                    page_index += 1
                    continue

                # Вариант 2: Текущий файл - одиночная страница
                if page_index + 1 < len(sorted_files):
                    next_file = sorted_files[page_index + 1]
                    next_path = os.path.join(input_folder, next_file)
                    next_page_num = get_page_number(next_file)
                    next_is_single = not is_likely_spread(next_path, DEFAULT_SPREAD_ASPECT_RATIO_THRESHOLD)

                    # Вариант 2.1: Следующий одиночный - СКЛЕИВАЕМ
                    if next_is_single:  # Сохраняем склейку как JPEG
                        output_filename = f"spread_{current_page_num:03d}-{next_page_num:03d}.jpg"
                        output_path = os.path.join(output_folder, output_filename)
                        status_msg = f"Создаю разворот: {current_file} + {next_file} -> {output_filename}"
                        self.root.after(0, lambda msg=status_msg: self.update_status(msg))
                        try:
                            img_left = Image.open(current_path)
                            img_right = Image.open(next_path)
                            width_left, height_left = img_left.size
                            width_right, height_right = img_right.size
                            total_width = width_left + width_right
                            max_height = max(height_left, height_right)
                            spread_img = Image.new('RGB', (total_width, max_height), DEFAULT_SPREAD_BG_COLOR)
                            spread_img.paste(img_left.convert('RGB'), (0, 0))
                            spread_img.paste(img_right.convert('RGB'), (width_left, 0))
                            spread_img.save(output_path, "JPEG", quality=95)
                            img_left.close()
                            img_right.close()
                            processed_count += 2
                        except Exception as e:
                            error_msg = f"Ошибка при создании разворота для {current_file} и {next_file}: {e}"
                            self.root.after(0, lambda msg=error_msg: self.update_status(msg))
                        page_index += 2
                        continue

                # Вариант 2.2: Текущая одиночная страница остается одна
                _, ext = os.path.splitext(current_file)
                output_filename = f"spread_{current_page_num:03d}{ext}"
                output_path = os.path.join(output_folder, output_filename)
                status_msg = f"Копирую одиночную страницу: {current_file} -> {output_filename}"
                self.root.after(0, lambda msg=status_msg: self.update_status(msg))
                try:
                    img = Image.open(current_path)
                    if img.format in ['JPEG', 'PNG', 'BMP', 'GIF', 'TIFF']:
                        if img.mode == 'RGBA' and img.format in ['PNG', 'GIF']:
                             img.save(output_path)
                        else:
                             img.convert('RGB').save(output_path)
                    else:
                        img.convert('RGB').save(output_path, "PNG")
                    img.close()
                    processed_count += 1
                except Exception as e:
                    error_msg = f"Ошибка при копировании одиночной {current_file}: {e}"
                    self.root.after(0, lambda msg=error_msg: self.update_status(msg))
                page_index += 1

            final_msg = f"Обработка завершена. Обработано {processed_count} файлов."
            self.root.after(0, lambda msg=final_msg: self.update_status(msg))
            self.root.after(0, lambda: messagebox.showinfo("Успех", "Создание разворотов завершено!"))

        except Exception as e:
            error_msg = f"Критическая ошибка при обработке: {e}"
            self.root.after(0, lambda msg=error_msg: self.update_status(msg))
            self.root.after(0, lambda: messagebox.showerror("Ошибка", f"Произошла критическая ошибка:\n{e}"))
        finally:
            self.root.after(0, lambda: self._set_buttons_state(tk.NORMAL))


    def _thread_run_all(self):
        self._thread_download()
        while self.download_button['state'] == tk.DISABLED:
             time.sleep(0.5)

        input_folder = self.pages_dir_entry.get().strip()
        if not os.path.isdir(input_folder) or not os.listdir(input_folder):
             self.root.after(0, lambda: self.update_status("Пропуск создания разворотов: папка со страницами пуста или не найдена."))
             self.root.after(0, lambda: messagebox.showwarning("Пропуск", "Скачивание не удалось или папка пуста. Создание разворотов пропущено."))
             self.root.after(0, lambda: self._set_buttons_state(tk.NORMAL))
             return

        if self._validate_processing_inputs():
             self._thread_process()
        else:
             self.root.after(0, lambda: self._set_buttons_state(tk.NORMAL))



if __name__ == "__main__":
    root = tk.Tk()
    app = JournalDownloaderApp(root)
    root.mainloop()
