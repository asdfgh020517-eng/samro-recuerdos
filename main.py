import os
import json
from typing import Optional, List
from fastapi import FastAPI, Form, Request, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
from authlib.integrations.starlette_client import OAuth
from supabase import create_client, Client

app = FastAPI()

app.add_middleware(SessionMiddleware, secret_key="clave_secreta_samro_2026")

os.makedirs("static/uploads", exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# CONFIGURACIÓN DE SUPABASE
SUPABASE_URL = "https://squbkdoruoxuxfkhuxdi.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InNxdWJrZG9ydW94dXhma2h1eGRpIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODUwMzAwMzgsImV4cCI6MjEwMDYwNjAzOH0.hbjf2dbc2S3hKNu9hQy-KsHnhJ1stvjCLgUtnj8ZK8M"
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# CONFIGURACIÓN DE GOOGLE OAUTH
GOOGLE_CLIENT_ID = "317422632908-a3ms0fnt3gunf69vkm62776h9p3sjum6.apps.googleusercontent.com"
GOOGLE_CLIENT_SECRET = "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"

oauth = OAuth()
oauth.register(
    name='google',
    client_id=GOOGLE_CLIENT_ID,
    client_secret=GOOGLE_CLIENT_SECRET,
    server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
    client_kwargs={'scope': 'openid email profile'}
)

ARCHIVAR_CRED = "credenciales.json"

def cargar_credenciales():
    if not os.path.exists(ARCHIVAR_CRED):
        default_cred = {"usuario": "admin", "password": "1234"}
        guardar_credenciales(default_cred)
        return default_cred
    with open(ARCHIVAR_CRED, "r", encoding="utf-8") as f:
        return json.load(f)

def guardar_credenciales(creds):
    with open(ARCHIVAR_CRED, "w", encoding="utf-8") as f:
        json.dump(creds, f, ensure_ascii=False, indent=4)

# --- SISTEMA DE ALMACENAMIENTO EN SUPABASE ---
def cargar_recuerdos(request: Request):
    try:
        response = supabase.table("recuerdos").select("*").order("id", desc=True).execute()
        data = response.data
        if data and len(data) > 0:
            return data
    except Exception as e:
        print("Error al cargar desde Supabase:", e)
    
    return [
        {
            "id": 1,
            "titulo": "Nuestro primer día",
            "fecha": "2026-01-01",
            "lugar": "Huancayo",
            "nota": "Un día super especial donde comenzamos este gran proyecto juntos.",
            "musica": "",
            "imagenes": [],
            "videos": []
        }
    ]

def subir_archivo_supabase(archivo: UploadFile, extensiones_video):
    if not archivo or not archivo.filename or archivo.filename.strip() == "":
        return None, False
    
    try:
        contenido = archivo.file.read()
        file_path = f"recuerdos_{archivo.filename}"
        
        supabase.storage.from_("multimedia").upload(
            path=file_path,
            file=contenido,
            file_options={"content-type": archivo.content_type or "application/octet-stream", "upsert": "true"}
        )
        
        public_url_res = supabase.storage.from_("multimedia").get_public_url(file_path)
        file_url = public_url_res
        
        es_video = (archivo.content_type and archivo.content_type.startswith("video")) or \
                   archivo.filename.lower().endswith(extensiones_video)
        return file_url, es_video
    except Exception as e:
        print("Error al subir archivo a Supabase Storage:", e)
        
    return None, False


@app.get("/", response_class=HTMLResponse)
def inicio(request: Request):
    if request.session.get("usuario"):
        return RedirectResponse(url="/muro", status_code=303)
    return RedirectResponse(url="/login", status_code=303)

@app.get("/login", response_class=HTMLResponse)
def vista_login(request: Request):
    return templates.TemplateResponse(request=request, name="login.html")

@app.post("/login")
def procesar_login(request: Request, usuario: str = Form(...), password: str = Form(...)):
    creds = cargar_credenciales()
    if usuario == creds.get("usuario") and password == creds.get("password"):
        request.session["usuario"] = usuario
        return RedirectResponse(url="/muro", status_code=303)
    else:
        return RedirectResponse(url="/login?error=1", status_code=303)

@app.get("/login/google")
async def login_google(request: Request):
    redirect_uri = request.url_for('auth_callback')
    if str(redirect_uri).startswith("http://"):
        redirect_uri = str(redirect_uri).replace("http://", "https://", 1)
    return await oauth.google.authorize_redirect(request, redirect_uri)

@app.get("/auth/callback")
async def auth_callback(request: Request):
    try:
        token = await oauth.google.authorize_access_token(request)
        user_info = await oauth.google.parse_id_token(request, token)
        if user_info and user_info.get("email"):
            email_usuario = user_info["email"]
            
            CORREOS_PERMITIDOS = [
                "asdfgh020517@gmail.com",
                "samyconozco2702@gmail.com"
            ]
            
            if email_usuario in CORREOS_PERMITIDOS:
                request.session["usuario"] = email_usuario
                return RedirectResponse(url="/muro", status_code=303)
            else:
                print(f"Acceso denegado para: {email_usuario}")
                
    except Exception as e:
        print("Error en Google Auth:", e)
        
    return RedirectResponse(url="/login?error=1", status_code=303)

@app.get("/logout")
def cerrar_sesion(request: Request):
    request.session.clear()
    return RedirectResponse(url="/login", status_code=303)

@app.get("/configuracion", response_class=HTMLResponse)
def vista_configuracion(request: Request):
    if not request.session.get("usuario"):
        return RedirectResponse(url="/login", status_code=303)
    
    creds = cargar_credenciales()
    return templates.TemplateResponse(
        request=request, 
        name="configuracion.html",
        context={
            "usuario_actual": creds.get("usuario"),
            "password_actual": creds.get("password")
        }
    )

@app.post("/actualizar-credenciales")
def actualizar_credenciales(
    request: Request, 
    usuario_nuevo: str = Form(...), 
    password_nueva: str = Form(...)
):
    if not request.session.get("usuario"):
        return RedirectResponse(url="/login", status_code=303)
    
    nuevas_creds = {
        "usuario": usuario_nuevo,
        "password": password_nueva
    }
    guardar_credenciales(nuevas_creds)
    return RedirectResponse(url="/configuracion?exito=1", status_code=303)

@app.get("/muro", response_class=HTMLResponse)
def muro(request: Request):
    if not request.session.get("usuario"):
        return RedirectResponse(url="/login", status_code=303)
        
    return templates.TemplateResponse(
        request=request, 
        name="muro.html", 
        context={}
    )

@app.get("/linea-del-tiempo", response_class=HTMLResponse)
def linea_del_tiempo(request: Request):
    if not request.session.get("usuario"):
        return RedirectResponse(url="/login", status_code=303)

    recuerdos = cargar_recuerdos(request)
    return templates.TemplateResponse(
        request=request, 
        name="linea.html", 
        context={"recuerdos": recuerdos}
    )

@app.post("/crear-recuerdo")
async def crear_recuerdo(
    request: Request,
    titulo: str = Form(...),
    fecha: str = Form(...),
    lugar: Optional[str] = Form(""),
    nota: str = Form(...),
    musica: Optional[str] = Form(""),
    archivos: List[UploadFile] = File(default=[])
):
    if not request.session.get("usuario"):
        return RedirectResponse(url="/login", status_code=303)

    rutas_imagenes = []
    rutas_videos = []
    EXT_VIDEOS = ('.mp4', '.mov', '.avi', '.mkv', '.webm')

    for archivo in archivos[:5]:
        url_archivo, es_video = subir_archivo_supabase(archivo, EXT_VIDEOS)
        if url_archivo:
            if es_video:
                rutas_videos.append(url_archivo)
            else:
                rutas_imagenes.append(url_archivo)

    nuevo_recuerdo = {
        "titulo": titulo,
        "fecha": fecha,
        "lugar": lugar,
        "nota": nota,
        "musica": musica,
        "imagenes": rutas_imagenes,
        "videos": rutas_videos
    }
    
    try:
        supabase.table("recuerdos").insert(nuevo_recuerdo).execute()
    except Exception as e:
        print("Error al insertar en Supabase:", e)

    return RedirectResponse(url="/linea-del-tiempo", status_code=303)

@app.delete("/recuerdos/{recuerdo_id}")
async def eliminar_recuerdo(request: Request, recuerdo_id: int):
    if not request.session.get("usuario"):
        return {"status": "error", "message": "No autorizado"}

    try:
        supabase.table("recuerdos").delete().eq("id", recuerdo_id).execute()
        return {"status": "success", "message": "Recuerdo eliminado"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.post("/recuerdos/{recuerdo_id}/editar")
async def editar_recuerdo(
    request: Request,
    recuerdo_id: int,
    titulo: str = Form(...),
    fecha: str = Form(...),
    lugar: Optional[str] = Form(""),
    nota: str = Form(...),
    musica: Optional[str] = Form(""),
    archivos: List[UploadFile] = File(default=[])
):
    if not request.session.get("usuario"):
        return RedirectResponse(url="/login", status_code=303)

    EXT_VIDEOS = ('.mp4', '.mov', '.avi', '.mkv', '.webm')
    nuevas_imgs = []
    nuevos_vids = []

    for archivo in archivos[:5]:
        url_archivo, es_video = subir_archivo_supabase(archivo, EXT_VIDEOS)
        if url_archivo:
            if es_video:
                nuevos_vids.append(url_archivo)
            else:
                nuevas_imgs.append(url_archivo)
            
    datos_actualizados = {
        "titulo": titulo,
        "fecha": fecha,
        "lugar": lugar,
        "nota": nota,
        "musica": musica
    }
    
    if nuevas_imgs or nuevos_vids:
        datos_actualizados["imagenes"] = nuevas_imgs
        datos_actualizados["videos"] = nuevos_vids

    try:
        supabase.table("recuerdos").update(datos_actualizados).eq("id", recuerdo_id).execute()
    except Exception as e:
        print("Error al actualizar en Supabase:", e)
        
    return RedirectResponse(url="/linea-del-tiempo", status_code=303)