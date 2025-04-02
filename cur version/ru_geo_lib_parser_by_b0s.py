import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import requests
import base64
import os
import re
import time
import threading
from PIL import Image, ImageTk

''' --- НАСТРОЙКИ --- '''
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


def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)



class JournalDownloaderApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Загрузчик + склейщик файлов из библиотеки РГО. v1.1 by b0s")
        self.root.minsize(600, 650)

        try:
            window_icon_path = resource_path("window_bnwbook.png")
            pil_icon = Image.open(window_icon_path)  # Защита от GC
            self.window_icon_image = ImageTk.PhotoImage(pil_icon)
            self.root.iconphoto(True, self.window_icon_image)
            print(f"DEBUG: Window icon path resolved to: {window_icon_path}")
        except Exception as e:
            print(f"Warning: Could not set window icon: {e}")

        self.stop_event = threading.Event()
        self.current_thread = None

        style = ttk.Style()
        style.configure("TLabel", padding=5)
        style.configure("TButton", padding=5)
        style.configure("TEntry", padding=5)
        style.configure("Stop.TButton", foreground="red", font=('Helvetica', 9, 'bold'))

        input_frame = ttk.LabelFrame(root, text="Параметры", padding=10)
        input_frame.pack(padx=10, pady=10, fill=tk.X)

        # Поля
        ttk.Label(input_frame, text="Базовый URL (до ID):").grid(row=0, column=0, sticky=tk.W)
        self.url_base_entry = ttk.Entry(input_frame, width=60)
        self.url_base_entry.grid(row=0, column=1, columnspan=2, sticky=tk.EW)
        self.url_base_entry.insert(0, "https://elib.rgo.ru/safe-view/")

        ttk.Label(input_frame, text="ID конкретного файла (через /):").grid(row=1, column=0, sticky=tk.W)
        self.url_ids_entry = ttk.Entry(input_frame, width=60)
        self.url_ids_entry.grid(row=1, column=1, columnspan=2, sticky=tk.EW)
        self.url_ids_entry.insert(0, "123456789/217168/1/")

        ttk.Label(input_frame, text="Имя файла на сайте:").grid(row=2, column=0, sticky=tk.W)
        self.pdf_filename_entry = ttk.Entry(input_frame, width=60)
        self.pdf_filename_entry.grid(row=2, column=1, columnspan=2, sticky=tk.EW)
        self.pdf_filename_entry.insert(0, "002_R.pdf")

        ttk.Label(input_frame, text="Кол-во страниц файла:").grid(row=3, column=0, sticky=tk.W)
        self.total_pages_entry = ttk.Entry(input_frame, width=10)
        self.total_pages_entry.grid(row=3, column=1, sticky=tk.W)
        self.total_pages_entry.insert(0, "56")

        ttk.Label(input_frame, text="Ваши Cookies (из DevTools):").grid(row=4, column=0, sticky=tk.W, pady=(5,0))
        self.cookies_entry = tk.Text(input_frame, height=4, width=60)
        self.cookies_entry.grid(row=5, column=0, columnspan=3, sticky=tk.EW, pady=(0,5))
        self.cookies_entry.insert(tk.END, "JSESSIONID=...; ym_uid=...; ym_d=...; ym_isad=...")

        # Пути
        path_frame = ttk.Frame(input_frame)
        path_frame.grid(row=6, column=0, columnspan=3, sticky=tk.EW)

        ttk.Label(path_frame, text="Папка для полученных страниц:").grid(row=0, column=0, sticky=tk.W)
        self.pages_dir_entry = ttk.Entry(path_frame, width=45)
        self.pages_dir_entry.grid(row=0, column=1, sticky=tk.EW, padx=(0, 5))
        self.pages_dir_entry.insert(0, "C:/downloaded_pages")  # НОВОЕ
        self.browse_pages_button = ttk.Button(path_frame, text="Обзор...", command=self.browse_output_pages)
        self.browse_pages_button.grid(row=0, column=2)

        ttk.Label(path_frame, text="Папка для созданных разворотов:").grid(row=1, column=0, sticky=tk.W)
        self.spreads_dir_entry = ttk.Entry(path_frame, width=45)
        self.spreads_dir_entry.grid(row=1, column=1, sticky=tk.EW, padx=(0, 5))
        self.spreads_dir_entry.insert(0, "C:/final_spreads")  # НОВОЕ
        self.browse_spreads_button = ttk.Button(path_frame, text="Обзор...", command=self.browse_output_spreads)
        self.browse_spreads_button.grid(row=1, column=2)

        path_frame.columnconfigure(1, weight=1)
        input_frame.columnconfigure(1, weight=1)

        # Кнопки
        control_frame = ttk.Frame(root, padding=10)
        control_frame.pack(fill=tk.X)

        self.run_all_button = ttk.Button(control_frame, text="Скачать и создать развороты", command=self.run_all)
        self.run_all_button.pack(side=tk.LEFT, padx=5)

        self.download_button = ttk.Button(control_frame, text="Только скачать страницы", command=self.run_download)
        self.download_button.pack(side=tk.LEFT, padx=5)

        self.process_button = ttk.Button(control_frame, text="Только создать развороты", command=self.run_processing)
        self.process_button.pack(side=tk.LEFT, padx=5)

        self.stop_button = ttk.Button(control_frame, text="СТОП", command=self.stop_action, state=tk.DISABLED, style="Stop.TButton")
        self.stop_button.pack(side=tk.RIGHT, padx=15) # НОВОЕ

        # Лог
        status_frame = ttk.LabelFrame(root, text="Статус", padding=10)
        status_frame.pack(padx=10, pady=10, fill=tk.BOTH, expand=True)

        self.status_text = scrolledtext.ScrolledText(status_frame, height=15, wrap=tk.WORD, state=tk.DISABLED)
        self.status_text.pack(fill=tk.BOTH, expand=True)


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

    def update_status(self, message):
        if not self.root.winfo_exists(): return # Не обновлять, если окно закрыто
        self.status_text.config(state=tk.NORMAL)
        self.status_text.insert(tk.END, message + "\n")
        self.status_text.see(tk.END)
        self.status_text.config(state=tk.DISABLED)
        self.root.update_idletasks()


    def clear_status(self):
        if not self.root.winfo_exists(): return
        self.status_text.config(state=tk.NORMAL)
        self.status_text.delete(1.0, tk.END)
        self.status_text.config(state=tk.DISABLED)


    def stop_action(self):  # НОВОЕ
        self.update_status("--- Получен СТОП ---")
        self.stop_event.set()
        self.stop_button.config(state=tk.DISABLED)


    def run_download(self):
        if not self._validate_download_inputs(): return
        self.clear_status()
        self._set_buttons_state(task_running=True)
        self.current_thread = threading.Thread(target=self._thread_download, daemon=True)
        self.current_thread.start()


    def run_processing(self):
        if not self._validate_processing_inputs(): return
        self.clear_status()
        self._set_buttons_state(task_running=True)
        self.current_thread = threading.Thread(target=self._thread_process, daemon=True)
        self.current_thread.start()


    def run_all(self):
        if not self._validate_download_inputs() or not self._validate_processing_inputs(check_dir_exists=False):
             return
        self.clear_status()
        self._set_buttons_state(task_running=True)
        self.current_thread = threading.Thread(target=self._thread_run_all, daemon=True)
        self.current_thread.start()


    def _set_buttons_state(self, task_running):  # НОВОЕ
        if not self.root.winfo_exists(): return

        state = tk.DISABLED if task_running else tk.NORMAL
        stop_state = tk.NORMAL if task_running else tk.DISABLED

        self.download_button.config(state=state)
        self.process_button.config(state=state)
        self.run_all_button.config(state=state)
        self.browse_pages_button.config(state=state)
        self.browse_spreads_button.config(state=state)
        # Кнопка СТОП имеет обратную логику 
        if not self.stop_event.is_set():
            self.stop_button.config(state=stop_state)

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


    def _validate_processing_inputs(self, check_dir_exists=True):
        pages_dir = self.pages_dir_entry.get().strip()
        spreads_dir = self.spreads_dir_entry.get().strip()
        if not pages_dir or not spreads_dir:
             messagebox.showerror("Ошибка ввода", "Пожалуйста, укажите папки для страниц и разворотов.")
             return False
        if check_dir_exists and not os.path.isdir(pages_dir):
             messagebox.showerror("Ошибка папки", f"Папка со страницами '{pages_dir}' не найдена.")
             return False
        return True


    def open_folder(self, folder_path):
        self.update_status(f"Попытка открыть папку: {folder_path}")
        try:
            norm_path = os.path.normpath(folder_path)
            if os.path.isdir(norm_path):
                os.startfile(norm_path)
            else:
                self.update_status(f"Ошибка: Папка не найдена: {norm_path}")
        except Exception as e:
            self.update_status(f"Ошибка при открытии папки '{norm_path}': {e}")

            
    # Логика выполнения в потоках
    def _thread_download(self):
        self.stop_event.clear()
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

            try:  # НОВОЕ
                os.makedirs(output_dir, exist_ok=True)
                self.root.after(0, lambda: self.update_status(f"Папка для страниц: '{output_dir}'"))
            except Exception as e:
                self.root.after(0, lambda: self.update_status(f"Ошибка создания папки '{output_dir}': {e}"))
                messagebox.showerror("Ошибка папки", f"Не удалось создать папку:\n{output_dir}\n{e}")
                return

            self.root.after(0, lambda: self.update_status(f"Начинаем скачивание {total_pages} страниц..."))

            session = requests.Session()
            session.headers.update(headers)
            session.cookies.update(cookies)

            success_count = 0
            for i in range(total_pages):
                if self.stop_event.is_set():  # НОВОЕ
                    self.root.after(0, lambda: self.update_status("--- Скачивание прервано пользователем ---"))
                    break

                page_string = f"{filename_pdf}/{i}"
                page_b64_bytes = base64.b64encode(page_string.encode('utf-8'))
                page_b64_string = page_b64_bytes.decode('utf-8')
                final_url = base_url + url_ids + page_b64_string
                base_output_filename = os.path.join(output_dir, f"page_{i:03d}")

                status_msg = f"Скачиваю страницу {i+1}/{total_pages}..."
                self.root.after(0, lambda msg=status_msg: self.update_status(msg))

                try:
                    response = session.get(final_url, timeout=30)
                    response.raise_for_status()

                    content_type = response.headers.get('Content-Type', '').lower()
                    extension = ".jpg"
                    if 'png' in content_type: extension = ".png"
                    elif 'gif' in content_type: extension = ".gif"
                    elif 'bmp' in content_type: extension = ".bmp"
                    elif 'tiff' in content_type: extension = ".tiff"

                    final_output_filename = base_output_filename + extension

                    with open(final_output_filename, 'wb') as f:
                        f.write(response.content)

                    if os.path.getsize(final_output_filename) == 0:
                        self.root.after(0, lambda name=final_output_filename: self.update_status(f"Предупреждение: Файл {os.path.basename(name)} пустой."))
                    else:
                         success_count += 1
                         self.root.after(0, lambda name=final_output_filename: self.update_status(f" -> Сохранено как {os.path.basename(name)}"))


                except requests.exceptions.RequestException as e:
                    error_msg = f"Ошибка сети/сервера на стр. {i+1}: {e}"
                    self.root.after(0, lambda msg=error_msg: self.update_status(msg))
                except Exception as e:
                    error_msg = f"Неожиданная ошибка на стр. {i+1}: {e}"
                    self.root.after(0, lambda msg=error_msg: self.update_status(msg))

                if self.stop_event.is_set():
                    self.root.after(0, lambda: self.update_status("--- Скачивание прервано пользователем (после запроса) ---"))
                    break
                time.sleep(DEFAULT_DELAY_SECONDS)


            if not self.stop_event.is_set():
                final_msg = f"Скачивание завершено. Успешно скачано {success_count} из {total_pages} страниц."
                self.root.after(0, lambda msg=final_msg: self.update_status(msg))
                folder_to_open = output_dir
                should_open = success_count > 0 # Открываем, если хоть что-то скачалось
                if should_open:
                    self.root.after(100, lambda path=folder_to_open: self.open_folder(path))
                if success_count == total_pages:
                    self.root.after(0, lambda: messagebox.showinfo("Успех", "Все страницы успешно скачаны!"))
                else:
                    self.root.after(0, lambda: messagebox.showwarning("Завершено с ошибками", f"Скачано {success_count} из {total_pages} страниц. Проверьте лог."))

        except Exception as e:
            error_msg = f"Критическая ошибка при скачивании: {e}"
            self.root.after(0, lambda msg=error_msg: self.update_status(msg))
            self.root.after(0, lambda: messagebox.showerror("Ошибка", f"Произошла критическая ошибка:\n{e}"))
        finally:
            self.stop_event.clear()
            self.current_thread = None
            self.root.after(0, lambda: self._set_buttons_state(task_running=False))

    def _thread_process(self):
        """Выполняет создание разворотов."""
        self.stop_event.clear()
        try:
            input_folder = self.pages_dir_entry.get().strip()
            output_folder = self.spreads_dir_entry.get().strip()
            image_extensions = ('.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff')

            try:
                os.makedirs(output_folder, exist_ok=True)
                self.root.after(0, lambda: self.update_status(f"Папка для разворотов: '{output_folder}'"))
            except Exception as e:
                self.root.after(0, lambda: self.update_status(f"Ошибка создания папки '{output_folder}': {e}"))
                messagebox.showerror("Ошибка папки", f"Не удалось создать папку:\n{output_folder}\n{e}")
                return

            self.root.after(0, lambda: self.update_status(f"Начинаем обработку изображений из '{input_folder}'..."))

            try:
                all_files = [f for f in os.listdir(input_folder) if f.lower().endswith(image_extensions)]
            except FileNotFoundError:
                self.root.after(0, lambda: self.update_status(f"Ошибка: Папка '{input_folder}' не найдена."))
                self.root.after(0, lambda: messagebox.showerror("Ошибка", f"Папка '{input_folder}' не найдена."))
                return

            sorted_files = sorted([f for f in all_files if get_page_number(f) != -1], key=get_page_number)

            if not sorted_files:
                self.root.after(0, lambda: self.update_status("В папке не найдено подходящих файлов изображений с номерами."))
                self.root.after(0, lambda: messagebox.showwarning("Нет файлов", "Не найдено файлов для обработки."))
                return

            self.root.after(0, lambda: self.update_status(f"Найдено {len(sorted_files)} файлов. Создание разворотов..."))

            page_index = 0
            processed_count = 0
            while page_index < len(sorted_files):
                if self.stop_event.is_set():
                    self.root.after(0, lambda: self.update_status("--- Обработка прервана пользователем ---"))
                    break

                current_file = sorted_files[page_index]
                current_path = os.path.join(input_folder, current_file)
                current_page_num = get_page_number(current_file)
                current_is_spread = page_index > 0 and is_likely_spread(current_path, DEFAULT_SPREAD_ASPECT_RATIO_THRESHOLD)

                # Вариант 1: Копирование обложки или готового разворота
                if current_is_spread or page_index == 0:
                    _, ext = os.path.splitext(current_file)
                    output_filename = f"spread_{current_page_num:03d}{ext}"
                    output_path = os.path.join(output_folder, output_filename)
                    status_msg = f"Копирую {'обложку' if page_index == 0 else 'готовый разворот'}: {current_file} -> {output_filename}"
                    self.root.after(0, lambda msg=status_msg: self.update_status(msg))
                    try:
                        # Просто чтобы сохранить метаданные и оригинал
                        import shutil
                        shutil.copy2(current_path, output_path)
                        processed_count += 1
                    except Exception as e:
                        error_msg = f"Ошибка при копировании {current_file}: {e}"
                        self.root.after(0, lambda msg=error_msg: self.update_status(msg))
                    page_index += 1
                    continue

                # Вариант 2: Попытка создать разворот из двух одиночных
                if page_index + 1 < len(sorted_files):
                    next_file = sorted_files[page_index + 1]
                    next_path = os.path.join(input_folder, next_file)
                    next_page_num = get_page_number(next_file)
                    next_is_single = not is_likely_spread(next_path, DEFAULT_SPREAD_ASPECT_RATIO_THRESHOLD)

                    # Вариант 2.1: Следующий тоже одиночный - СКЛЕИВАЕМ К СРЕДНЕЙ ВЫСОТЕ
                    if next_is_single:
                        output_filename = f"spread_{current_page_num:03d}-{next_page_num:03d}.jpg"
                        output_path = os.path.join(output_folder, output_filename)
                        status_msg = f"Создаю разворот (к средней высоте): {current_file} + {next_file} -> {output_filename}"
                        self.root.after(0, lambda msg=status_msg: self.update_status(msg))
                        try:
                            img_left = Image.open(current_path)
                            img_right = Image.open(next_path)
                            w_left, h_left = img_left.size
                            w_right, h_right = img_right.size

                            # Масштабирование по LANCZOS
                            if h_left == h_right:
                                target_height = h_left
                                img_left_final = img_left
                                img_right_final = img_right
                                w_left_final = w_left
                                w_right_final = w_right
                            else:
                                target_height = (h_left + h_right) // 2
                                self.root.after(0, lambda h=target_height: self.update_status(f"   (Целевая высота: {h}px)"))

                                ratio_left = target_height / h_left
                                w_left_final = int(w_left * ratio_left)
                                img_left_final = img_left.resize((w_left_final, target_height), Image.Resampling.LANCZOS)
                                if h_left != target_height:
                                     self.root.after(0, lambda f=current_file: self.update_status(f"   (Изменен размер {f})"))

                                ratio_right = target_height / h_right
                                w_right_final = int(w_right * ratio_right)
                                img_right_final = img_right.resize((w_right_final, target_height), Image.Resampling.LANCZOS)
                                if h_right != target_height:
                                     self.root.after(0, lambda f=next_file: self.update_status(f"   (Изменен размер {f})"))

                            total_width = w_left_final + w_right_final
                            spread_img = Image.new('RGB', (total_width, target_height))

                            spread_img.paste(img_left_final.convert('RGB'), (0, 0))
                            spread_img.paste(img_right_final.convert('RGB'), (w_left_final, 0))

                            spread_img.save(output_path, "JPEG", quality=95)
                            img_left.close()
                            img_right.close()
                            processed_count += 2
                        except Exception as e:
                            error_msg = f"Ошибка при создании разворота для {current_file} и {next_file}: {e}"
                            self.root.after(0, lambda msg=error_msg: self.update_status(msg))
                        page_index += 2
                        continue

                # Вариант 2.2: Текущая одиночная страница остается одна (копируем как есть)
                _, ext = os.path.splitext(current_file)
                output_filename = f"spread_{current_page_num:03d}{ext}"
                output_path = os.path.join(output_folder, output_filename)
                status_msg = f"Копирую одиночную страницу: {current_file} -> {output_filename}"
                self.root.after(0, lambda msg=status_msg: self.update_status(msg))
                try:
                    import shutil
                    shutil.copy2(current_path, output_path)
                    processed_count += 1
                except Exception as e:
                    error_msg = f"Ошибка при копировании одиночной {current_file}: {e}"
                    self.root.after(0, lambda msg=error_msg: self.update_status(msg))
                page_index += 1


            if not self.stop_event.is_set():
                final_msg = f"Обработка завершена. Обработано/скопировано {processed_count} файлов."
                self.root.after(0, lambda msg=final_msg: self.update_status(msg))
                folder_to_open = output_folder
                should_open = processed_count > 0
                if should_open:
                    self.root.after(100, lambda path=folder_to_open: self.open_folder(path))
                self.root.after(0, lambda: messagebox.showinfo("Успех", "Создание разворотов завершено!"))

        except Exception as e:
            error_msg = f"Критическая ошибка при обработке: {e}"
            self.root.after(0, lambda msg=error_msg: self.update_status(msg))
            self.root.after(0, lambda: messagebox.showerror("Ошибка", f"Произошла критическая ошибка:\n{e}"))
        finally:
            self.stop_event.clear()
            self.current_thread = None
            self.root.after(0, lambda: self._set_buttons_state(task_running=False))


    def _thread_run_all(self):
        self._thread_download()
        while self.current_thread is not None and self.current_thread.is_alive():
             time.sleep(0.5)

        if self.stop_event.is_set():
             self.root.after(0, lambda: self.update_status("--- Запуск обработки отменен из-за остановки скачивания ---"))
             self.root.after(0, lambda: self._set_buttons_state(task_running=False))
             return

        input_folder = self.pages_dir_entry.get().strip()
        if not os.path.isdir(input_folder) or not os.listdir(input_folder):
             self.root.after(0, lambda: self.update_status("Пропуск создания разворотов: папка со страницами пуста или не найдена."))
             self.root.after(0, lambda: messagebox.showwarning("Пропуск", "Скачивание не удалось или папка пуста. Создание разворотов пропущено."))
             self.root.after(0, lambda: self._set_buttons_state(task_running=False))
             return

        if self._validate_processing_inputs():
             # Чтобы основной поток GUI не блокировался ожиданием
             self._set_buttons_state(task_running=True)
             self.current_thread = threading.Thread(target=self._thread_process, daemon=True)
             self.current_thread.start()
        else:
             self.root.after(0, lambda: self._set_buttons_state(task_running=False))



if __name__ == "__main__":
    root = tk.Tk()
    app = JournalDownloaderApp(root)
    root.mainloop()
