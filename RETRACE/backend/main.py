from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from database import Base, engine
from models.trace import Trace
from models.trace_event import TraceEvent
from routes.trace import router as trace_router
from routes.inventory import router as inventory_router
from routes.payment import router as payment_router
from routes.order import router as order_router
from models.inventory import InventoryItem
from services.inventory_service import initialize_inventory
from models.order import Order
Base.metadata.create_all(bind=engine)


app = FastAPI(
    title="RETRACE API",
    description="Backend API for the RETRACE system",
    version="1.0.0"
)

Base.metadata.create_all(bind=engine)
initialize_inventory()


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(trace_router)
app.include_router(inventory_router)
app.include_router(payment_router)
app.include_router(order_router)


@app.get("/")
def home():
    return {
        "message": "RETRACE Backend is Working!",
        "status": "success"
    }


@app.get("/health")
def health_check():
    return {
        "status": "healthy"
    }