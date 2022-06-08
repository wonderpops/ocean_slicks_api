from email.mime import image
from fastapi import FastAPI, HTTPException, Depends, Request, File, UploadFile
from fastapi.responses import JSONResponse, FileResponse
from fastapi_jwt_auth import AuthJWT
from fastapi_jwt_auth.exceptions import AuthJWTException
from pydantic import BaseModel
from app.db import database
from fastapi.middleware.cors import CORSMiddleware
from passlib.context import CryptContext
from fastapi.security import OAuth2PasswordBearer
import time
from app.models import *
import uuid
import os

IMAGEDIR = "users-images/"

ACCESS_TOKEN_EXPIRE_SECONDS = 180

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

app = FastAPI()
app.state.database = database


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def startup() -> None:
    database_ = app.state.database
    if not database_.is_connected:
        await database_.connect()


@app.on_event("shutdown")
async def shutdown() -> None:
    database_ = app.state.database
    if database_.is_connected:
        await database_.disconnect()


class Settings(BaseModel):
    authjwt_secret_key: str = os.environ['API_SECRET_KEY']
    authjwt_access_token_expires: int = ACCESS_TOKEN_EXPIRE_SECONDS
    authjwt_refresh_token_expires: bool = False


def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password):
    return pwd_context.hash(password)


# callback to get your configuration
@AuthJWT.load_config
def get_config():
    return Settings()

# exception handler for authjwt
# in production, you can tweak performance using orjson response
@app.exception_handler(AuthJWTException)
def authjwt_exception_handler(request: Request, exc: AuthJWTException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.message}
    )


@app.post('/login')
async def login(username, password, Authorize: AuthJWT = Depends()):
    user = await User.objects.get_or_none(username=username)
    if user:
        if verify_password(password, user.hashed_password):
            access_token = Authorize.create_access_token(subject=username)
            refresh_token = Authorize.create_refresh_token(subject=username)
            # response.set_cookie(key="access_token", value={access_token}, httponly=True, secure=True)
            # response.set_cookie(key="access_token", value={access_token}, httponly=True, secure=True)
            return {"access_token": access_token,
                    "refresh_token": refresh_token,
                    "expires_at": round(time.time() + ACCESS_TOKEN_EXPIRE_SECONDS)}
        else:
            raise HTTPException(status_code=401, detail="Incorrect email or password")
    else:
        raise HTTPException(status_code=401, detail="Incorrect email or password")


@app.post('/refresh')
def refresh(authorize: AuthJWT = Depends()):
    authorize.jwt_refresh_token_required()

    current_user = authorize.get_jwt_subject()
    new_access_token = authorize.create_access_token(subject=current_user)
    refresh_token = authorize.create_refresh_token(subject=current_user)
    return {"access_token": new_access_token, "refresh_token": refresh_token, "expires_at": round(time.time() + ACCESS_TOKEN_EXPIRE_SECONDS)}


@app.post('/signup', response_model=User)
async def signup(username, email, password, authorize: AuthJWT = Depends()):
    hashed_password = get_password_hash(password)
    user = User(username=username, email=email, hashed_password=hashed_password)
    await user.save()
    return user


@app.post("/upload_image")
async def upload_image(file: UploadFile = File(...)):

    file.filename = f"{uuid.uuid4()}.jpg"
    contents = await file.read()


    with open(f"{IMAGEDIR}{file.filename}", "wb") as f:
        f.write(contents)

    return file.filename


@app.post("/upload_image_data", response_model=Image)
async def upload_image(image_data: Image):

    return await image_data.save()


@app.get("/get_image")
async def get_image_by_name(file_name):

    path = f"{IMAGEDIR}{file_name}"
    
    return FileResponse(path)


@app.get("/get_image_data", response_model=Image)
async def get_image_data(id: int):

    image_data = await Image.objects.get_or_none(id=id)
    
    return image_data

requested_post = Post.get_pydantic(exclude={'user', 'created_at'})
response_post = Post.get_pydantic(exclude={'user': {'email','disabled','hashed_password'}, 'images': {'post'}})

@app.post("/add_post")
async def add_post(post_data: requested_post, Authorize: AuthJWT = Depends()):
    Authorize.jwt_required()

    current_user_name = Authorize.get_jwt_subject()
    print(current_user_name)
    current_user = await User.objects.get(username=current_user_name)
    
    post = Post(**post_data.dict())
    post.user = current_user
    post = await post.save()
    
    for img in post.images:
        await img.save()
    return JSONResponse(status_code=200, content={"message": "Post uploaded"})


@app.get("/get_all_posts", response_model=List[response_post])
async def get_all_posts():
    posts = await Post.objects.select_all(follow=True).order_by("-id").all()   
    return posts


@app.get("/get_posts_in_bounds", response_model=List[response_post])
async def get_posts_in_bounds(min_lat: float, min_lng: float, max_lat: float, max_lng: float):
    response_posts = []
    posts = await Post.objects.select_all(follow=False).order_by("-id").all() 
    for post in posts:
        if post.images[0].latitude > min_lat and  post.images[0].latitude < max_lat and post.images[0].longitude > min_lng and post.images[0].longitude < max_lng:
            response_posts.append(post)
    return response_posts


@app.get("/get_post", response_model=response_post)
async def get_post_by_id(id: int):
    post = await Post.objects.select_all(follow=True).get(id=id)
    return post

@app.get("/get_all_images", response_model=List[Image])
async def get_all_images():

    images = await Image.objects.select_all(follow=True).all()   
    return images


@app.get('/user', response_model=User)
def user(Authorize: AuthJWT = Depends()):
    Authorize.jwt_required()

    current_user = Authorize.get_jwt_subject()
    return current_user