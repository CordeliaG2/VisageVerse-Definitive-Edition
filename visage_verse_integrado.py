import importlib
import subprocess
import sys

def ensure_package(module_name, package_name=None):
    """
    Verifica si un paquete está instalado, y si no, lo instala automáticamente con pip.
    """
    package_name = package_name or module_name
    try:
        importlib.import_module(module_name)
        print(f"✅ {package_name} ya está instalado.")
    except ImportError:
        print(f"📦 Instalando {package_name}...")
        try:
            result = subprocess.run(
                [sys.executable, "-m", "pip", "install", "--upgrade", package_name],
                check=True,
                capture_output=True,
                text=True
            )
            print(result.stdout)
            print(f"✅ {package_name} instalado correctamente.")
        except subprocess.CalledProcessError as e:
            print(f"❌ Error instalando {package_name}:")
            print(e.stderr)
            print("Intenta instalarlo manualmente ejecutando:")
            print(f"    {sys.executable} -m pip install {package_name}")
            sys.exit(1)  # Sale si no puede instalar

# --- Verificar dependencias ---
ensure_package("cv2", "opencv-contrib-python")
ensure_package("numpy")


import cv2
import os
import numpy as np
import tkinter as tk
import time
import threading
from threading import Thread
from datetime import datetime, timedelta

# --- Integración Control de Acceso ---
from control_acceso_integration import (
    init_access_db,
    scan_qr_frame,
    open_access_admin_window,
    open_user_registration_window
)

TIEMPO_ENTRE_DETECCIONES = 60
ultima_deteccion = None
persona_detectada = ""
archivo_creado = False
estado_personas = {}

def mostrar_informacion(persona, estado):
    if persona is not None:
        evento = "Entrada" if estado else "Salida"
        fecha_hora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        informacion = f"Persona: {persona}\nFecha y hora: {fecha_hora}\nEstado: {evento}"
        print(informacion)

def guardar_en_archivo(persona, estado):
    if persona is not None:
        evento = "Entrada" if estado else "Salida"
        fecha_hora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open("detecciones.txt", "a") as file:
            file.write(f"Persona detectada: {persona}, Fecha y hora: {fecha_hora},{evento}\n")

def center_window(window):
    window.update_idletasks()
    width = window.winfo_width()
    height = window.winfo_height()
    x = (window.winfo_screenwidth() // 2) - (width // 2)
    y = (window.winfo_screenheight() // 2) - (height // 2)
    window.geometry(f'{width}x{height}+{x}+{y}')

def solicitar_nombre_apellido():
    ventana_nombre_apellido = tk.Toplevel(ventana)
    ventana_nombre_apellido.title("Ingresar nombre y apellido")

    etiqueta_nombre = tk.Label(ventana_nombre_apellido, text="Nombre:")
    etiqueta_nombre.pack()
    entry_nombre = tk.Entry(ventana_nombre_apellido)
    entry_nombre.pack()

    etiqueta_apellido = tk.Label(ventana_nombre_apellido, text="Apellido:")
    etiqueta_apellido.pack()
    entry_apellido = tk.Entry(ventana_nombre_apellido)
    entry_apellido.pack()

    def guardar_nombre_apellido():
        nombre = entry_nombre.get()
        apellido = entry_apellido.get()
        global personName
        personName = f"{nombre}_{apellido}"
        ventana_nombre_apellido.destroy()
        case2()

    def entrenar_sin_fotos():
        case4()

    tk.Button(ventana_nombre_apellido, text="Guardar", command=guardar_nombre_apellido).pack()
    tk.Button(ventana_nombre_apellido, text="Entrenar sin fotos", command=entrenar_sin_fotos).pack()

def cargar_modelo():
    global face_recognizer, etiqueta_estado
    face_recognizer = cv2.face.LBPHFaceRecognizer_create()
    if os.path.exists('models/modeloLBPHFace.xml'):
        face_recognizer.read('models/modeloLBPHFace.xml')
        print("Modelo cargado exitosamente")
        etiqueta_estado.config(text="Modelo cargado exitosamente")
        boton_reconocimiento.config(state=tk.NORMAL)

def abrir_modo_reconocimiento():
    case1()

def abrir_modo_entrenamiento():
    solicitar_nombre_apellido()

def case1():
    from control_acceso_integration import scan_qr_frame, mostrar_notificacion, dibujar_notificacion
    global persona_detectada, archivo_creado, ultima_deteccion, estado_personas
    dataPath = 'Data'
    if not os.path.exists('models/modeloLBPHFace.xml'):
        print("Modelo no encontrado. Entrena primero.")
        return

    imagePaths = os.listdir(dataPath)
    faceClassif = cv2.CascadeClassifier('models/haarcascade_frontalface_default.xml')
    cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)

    while True:
        ret, frame = cap.read()
        if not ret:
            break
        frame = cv2.flip(frame, 1)
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        auxFrame = gray.copy()
        faces = faceClassif.detectMultiScale(gray, 1.3, 5)
        persona = None

        # --- NUEVO: lectura de QR integrada ---
        scan_qr_frame(frame)

        for (x, y, w, h) in faces:
            cv2.rectangle(frame, (x, y), (x+w, y+h), (255, 0, 0), 2)
            rostro = auxFrame[y:y+h, x:x+w]
            rostro = cv2.resize(rostro, (150, 150), interpolation=cv2.INTER_CUBIC)
            result = face_recognizer.predict(rostro)

            if result[1] < 70:
                index = result[0]
                if 0 <= index < len(imagePaths):
                    persona = imagePaths[index]
                    cv2.putText(frame, f'{persona}', (x, y-25), 2, 1.1, (0, 255, 0), 1, cv2.LINE_AA)
                    cv2.rectangle(frame, (x, y), (x+w, y+h), (0, 255, 0), 2)
                    if ultima_deteccion is None or datetime.now() - ultima_deteccion >= timedelta(seconds=TIEMPO_ENTRE_DETECCIONES):
                        estado = not estado_personas.get(persona, False)
                        print(f"Persona detectada: {persona}")
                        Thread(target=guardar_en_archivo, args=(persona, estado), daemon=True).start()
                        ultima_deteccion = datetime.now()
                        estado_personas[persona] = estado
                        threading.Thread(target=mostrar_informacion, args=(persona, estado), daemon=True).start()
                        evento = "ENTRADA" if estado else "SALIDA"
                        mostrar_notificacion(frame, f"{persona} ({evento})", (0, 255, 255))

            else:
                cv2.putText(frame, 'Desconocido', (x, y-20), 2, 0.8, (0, 0, 255), 1, cv2.LINE_AA)
                cv2.rectangle(frame, (x, y), (x+w, y+h), (0, 0, 255), 2)

        dibujar_notificacion(frame)
        cv2.imshow('Reconocimiento Facial + QR', frame)
        k = cv2.waitKey(1)
        if k == 27:
            break

    cap.release()
    cv2.destroyAllWindows()

def case2():
    global personName
    dataPath = 'Data'
    personPath = dataPath + '/' + personName

    if not os.path.exists(personPath):
        print('Carpeta creada: ', personPath)
        os.makedirs(personPath)

    face_cascade = cv2.CascadeClassifier("models/haarcascade_frontalface_default.xml")
    cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
    count = 0

    while True:
        _, img = cap.read()
        img = cv2.flip(img, 1)
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        auxFrame = img.copy()
        faces = face_cascade.detectMultiScale(gray, 1.3, 5)

        for (x, y, w, h) in faces:
            cv2.rectangle(img, (x, y), (x+w, y+h), (255, 0, 0), 2)
            rostro = auxFrame[y:y+h, x:x+w]
            rostro = cv2.resize(rostro, (150, 150), interpolation=cv2.INTER_CUBIC)
            cv2.imwrite(personPath + f'/rostro_{count}.jpg', rostro)
            count += 1

        cv2.imshow('Captura de Rostros', img)
        k = cv2.waitKey(1)
        if k == 27 or count >= 100:
            break

    cap.release()
    cv2.destroyAllWindows()
    print("Entrenando modelo...")

    peopleList = os.listdir(dataPath)
    labels = []
    facesData = []
    label = 0
    for nameDir in peopleList:
        personPath = dataPath + '/' + nameDir
        for fileName in os.listdir(personPath):
            labels.append(label)
            facesData.append(cv2.imread(personPath + '/' + fileName, 0))
        label += 1

    face_recognizer = cv2.face.LBPHFaceRecognizer_create()
    face_recognizer.train(facesData, np.array(labels))
    os.makedirs('models', exist_ok=True)
    face_recognizer.write('models/modeloLBPHFace.xml')
    print("Modelo entrenado y almacenado.")

def case3():
    faceClassif = cv2.CascadeClassifier('models/haarcascade_frontalface_default.xml')
    cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
    while True:
        _, image = cap.read()
        image = cv2.flip(image, 1)
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        faces = faceClassif.detectMultiScale(gray, 1.1, 4)
        cv2.putText(image, 'Modo seguro activo', (10, 20), 2, 0.5, (128, 0, 255), 1, cv2.LINE_AA)
        for (x, y, w, h) in faces:
            cv2.rectangle(image, (x, y), (x+w, y+h), (255, 0, 0), 2)
        cv2.imshow('image', image)
        k = cv2.waitKey(1)
        if k == 27:
            break
    cap.release()
    cv2.destroyAllWindows()

def case4():
    dataPath = 'Data'
    peopleList = os.listdir(dataPath)
    print('Lista de personas: ', peopleList)

    labels = []
    facesData = []
    label = 0

    for nameDir in peopleList:
        personPath = dataPath + '/' + nameDir
        print('Leyendo las imágenes')

        for fileName in os.listdir(personPath):
            print('Rostros: ', nameDir + '/' + fileName)
            labels.append(label)
            facesData.append(cv2.imread(personPath+'/'+fileName,0))
        label = label + 1

    face_recognizer = cv2.face.LBPHFaceRecognizer_create()

    print("Entrenando...")
    face_recognizer.train(facesData, np.array(labels))

    face_recognizer.write('models/modeloLBPHFace.xml')
    print("Modelo almacenado...")
    cv2.destroyAllWindows()

def main():
    global ventana, etiqueta_estado, boton_reconocimiento

    init_access_db()  # Inicializa la base de datos del control de acceso

    hilo_carga_modelo = Thread(target=cargar_modelo)
    hilo_carga_modelo.start()

    ventana = tk.Tk()
    ventana.title("Visage Verse - Integrado con Control de Acceso")

    tk.Label(ventana, text="Selecciona una opción:").pack()

    boton_reconocimiento = tk.Button(ventana, text="Modo Reconocimiento", command=abrir_modo_reconocimiento, state=tk.DISABLED)
    boton_reconocimiento.pack()

    tk.Button(ventana, text="Modo Entrenamiento", command=abrir_modo_entrenamiento).pack()
    tk.Button(ventana, text="Opción 3", command=case3).pack()

    # --- NUEVOS BOTONES PARA CONTROL DE ACCESO ---
    tk.Button(ventana, text="Registrar Usuario/QR", command=open_user_registration_window, bg="#4B0082", fg="white").pack(pady=5)
    tk.Button(ventana, text="Admin Control Acceso", command=open_access_admin_window, bg="#4B0082", fg="white").pack(pady=5)

    etiqueta_estado = tk.Label(ventana, text="Estado del modelo: Cargando...")
    etiqueta_estado.pack()

    ventana.mainloop()

if __name__ == "__main__":
    main()
