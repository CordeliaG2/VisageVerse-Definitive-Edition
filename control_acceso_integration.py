import os
import sqlite3
from datetime import datetime
import cv2
from pyzbar import pyzbar
import tkinter as tk
from tkinter import ttk, messagebox
import qrcode
import numpy as np
from threading import Thread

# --- Control de tiempo para detección de QR ---
TIEMPO_ENTRE_QR = 60  # segundos entre detecciones del mismo QR
ultima_deteccion_qr = {}  # {plate: datetime}

# --- NOTIFICACIONES VISUALES ---
notificacion_activa = {"texto": "", "tiempo": 0, "color": (0, 255, 0)}

def mostrar_notificacion(frame, texto, color=(0, 255, 0), duracion=2.5):
    """
    Muestra una notificación visual tipo 'toast' sobre el frame.
    """
    global notificacion_activa
    notificacion_activa["texto"] = texto
    notificacion_activa["tiempo"] = datetime.now().timestamp() + duracion
    notificacion_activa["color"] = color

def dibujar_notificacion(frame):
    """
    Dibuja la notificación actual en pantalla si sigue activa.
    """
    global notificacion_activa
    if datetime.now().timestamp() < notificacion_activa["tiempo"]:
        h, w, _ = frame.shape
        texto = notificacion_activa["texto"]
        color = notificacion_activa["color"]

        # Fondo semitransparente tipo Minecraft
        overlay = frame.copy()
        alto = 60
        cv2.rectangle(overlay, (10, 10), (w - 10, 10 + alto), (0, 0, 0), -1)
        frame[:] = cv2.addWeighted(overlay, 0.5, frame, 0.5, 0)

        # Texto con borde
        cv2.putText(frame, texto, (30, 50), cv2.FONT_HERSHEY_DUPLEX, 1, (0, 0, 0), 5, cv2.LINE_AA)
        cv2.putText(frame, texto, (30, 50), cv2.FONT_HERSHEY_DUPLEX, 1, color, 2, cv2.LINE_AA)


# --- CONFIGURACIÓN BASE ---
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DB_PATH = os.path.join(BASE_DIR, "access_control.db")
QR_FOLDER = os.path.join(BASE_DIR, "qrcodes")

# --- BASE DE DATOS ---
def init_access_db():
    """Crea la base de datos y tablas si no existen."""
    os.makedirs(QR_FOLDER, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            vehicle_type TEXT NOT NULL,
            plate TEXT UNIQUE NOT NULL,
            qr_path TEXT NOT NULL
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS access_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            timestamp TEXT NOT NULL,
            event TEXT NOT NULL,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
    """)
    conn.commit()
    conn.close()
    print(f"[DB] Base de datos inicializada en: {DB_PATH}")

# --- FUNCIONES DE LOG ---
def log_event(user_id, event):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute(
        "INSERT INTO access_log (user_id, timestamp, event) VALUES (?, ?, ?)",
        (user_id, ts, event)
    )
    conn.commit()
    conn.close()
    print(f"[LOG] Usuario {user_id} → {event} ({ts})")

# --- DETECCIÓN DE QR ---
def scan_qr_frame(frame):
    """
    Escanea códigos QR en el frame y aplica control de tiempo entre detecciones.
    """
    global ultima_deteccion_qr

    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    decoded_objects = pyzbar.decode(gray)

    if not decoded_objects:
        dibujar_notificacion(frame)
        return

    # Abrir conexión a la base de datos
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    for obj in decoded_objects:
        code = obj.data.decode().strip()
        now = datetime.now()

        # Control de tiempo entre detecciones
        if code in ultima_deteccion_qr:
            delta = (now - ultima_deteccion_qr[code]).total_seconds()
            if delta < TIEMPO_ENTRE_QR:
                continue  # aún dentro del intervalo, ignorar

        # Buscar en la base de datos
        cursor.execute('SELECT id, name, vehicle_type, plate FROM users WHERE plate=?', (code,))
        user = cursor.fetchone()

        if user:
            uid, name, vt, pl = user
            cursor.execute('SELECT event FROM access_log WHERE user_id=? ORDER BY id DESC LIMIT 1', (uid,))
            last = cursor.fetchone()
            ev = 'entrada' if not last or last[0] == 'salida' else 'salida'

            log_event(uid, ev)
            ultima_deteccion_qr[code] = now

            texto = f"{name} ({ev.upper()}) [{pl}]"
            color = (0, 255, 0) if ev == "entrada" else (0, 0, 255)
            mostrar_notificacion(frame, texto, color)
            print(f"[QR] Detectado: {texto}")

            # Dibujar borde del QR detectado
            (x, y, w, h) = obj.rect
            cv2.rectangle(frame, (x, y), (x + w, y + h), color, 2)
            cv2.putText(frame, f"{name}", (x, y - 10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2, cv2.LINE_AA)
        else:
            # QR desconocido
            (x, y, w, h) = obj.rect
            cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 0, 255), 2)
            cv2.putText(frame, "QR no registrado", (x, y - 10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2, cv2.LINE_AA)

    conn.close()

    # Mostrar notificación activa
    dibujar_notificacion(frame)

# --- REGISTRO DE USUARIOS ---
def open_user_registration_window():
    """Ventana emergente para registrar usuario y generar QR."""
    win = tk.Toplevel()
    win.title("Registrar Usuario - Control de Acceso")

    tk.Label(win, text="Nombre:").grid(row=0, column=0, padx=5, pady=5)
    e_name = tk.Entry(win)
    e_name.grid(row=0, column=1, padx=5, pady=5)

    tk.Label(win, text="Vehículo:").grid(row=1, column=0, padx=5, pady=5)
    e_vehicle = ttk.Combobox(win, values=["Carro", "Moto"], state="readonly")
    e_vehicle.grid(row=1, column=1, padx=5, pady=5)

    tk.Label(win, text="Placa (sin espacios):").grid(row=2, column=0, padx=5, pady=5)
    e_plate = tk.Entry(win)
    e_plate.grid(row=2, column=1, padx=5, pady=5)

    def save():
        name = e_name.get().strip()
        vt = e_vehicle.get().strip()
        plate = e_plate.get().strip().upper()

        if not name or not vt or not plate:
            messagebox.showwarning("Campos incompletos", "Por favor completa todos los campos.")
            return

        qr_path = os.path.join(QR_FOLDER, f"{plate}.png")

        try:
            # Crear código QR
            qr_img = qrcode.make(plate)
            qr_img.save(qr_path)

            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO users (name, vehicle_type, plate, qr_path) VALUES (?, ?, ?, ?)",
                (name, vt, plate, qr_path)
            )
            conn.commit()
            conn.close()

            messagebox.showinfo("Usuario registrado", f"Se generó el QR para {name}.\nArchivo: {qr_path}")
            print(f"[DB] Usuario {name} ({plate}) guardado y QR generado.")
        except sqlite3.IntegrityError:
            messagebox.showerror("Error", f"La placa '{plate}' ya existe en la base de datos.")
        except Exception as e:
            messagebox.showerror("Error", f"Ocurrió un error: {e}")

    tk.Button(win, text="Registrar", command=save, bg="#6A1B9A", fg="white").grid(row=3, column=0, columnspan=2, pady=10)

# --- ADMINISTRADOR DE REGISTROS ---
def open_access_admin_window():
    """Ventana para ver el historial de accesos."""
    win = tk.Toplevel()
    win.title("Historial de Accesos - Control de Acceso")

    cols = ("ID", "Usuario", "Fecha", "Evento")
    tree = ttk.Treeview(win, columns=cols, show="headings")
    for c in cols:
        tree.heading(c, text=c)
        tree.column(c, width=120, anchor="center")
    tree.pack(fill="both", expand=True)

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    data = cursor.execute("""
        SELECT l.id, u.name, l.timestamp, l.event
        FROM access_log l
        JOIN users u ON u.id = l.user_id
        ORDER BY l.id DESC
    """).fetchall()
    conn.close()

    if not data:
        messagebox.showinfo("Sin registros", "No hay eventos de acceso aún.")
    else:
        for row in data:
            tree.insert("", tk.END, values=row)
