import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List, Optional, Any, Dict

from database import db, create_document, get_documents
from bson import ObjectId

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ----------------------------
# Helpers
# ----------------------------
class PyObjectId(ObjectId):
    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, v):
        if isinstance(v, ObjectId):
            return v
        if not ObjectId.is_valid(v):
            raise ValueError("Invalid objectid")
        return ObjectId(v)

def serialize_doc(doc: Dict[str, Any]) -> Dict[str, Any]:
    if not doc:
        return doc
    d = {**doc}
    if "_id" in d:
        d["id"] = str(d.pop("_id"))
    return d


# ----------------------------
# Schemas
# ----------------------------
class ProductIn(BaseModel):
    title: str
    description: Optional[str] = None
    price: float = Field(..., ge=0)
    currency: str = Field("INR")
    category: str
    images: List[str] = []
    materials: List[str] = []
    stock: int = 0
    vendor: Optional[str] = None
    artisanStory: Optional[str] = None

class OrderItem(BaseModel):
    productId: str
    title: str
    qty: int = Field(..., ge=1)
    unitPrice: float = Field(..., ge=0)

class Customer(BaseModel):
    name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None

class OrderIn(BaseModel):
    customer: Customer
    items: List[OrderItem]
    subtotal: float
    shipping: float = 0
    total: float
    status: str = "received"


# ----------------------------
# Routes
# ----------------------------
@app.get("/")
def read_root():
    return {"message": "Flames.Blue API running"}


@app.get("/api/products")
def list_products(category: Optional[str] = None, q: Optional[str] = None, limit: int = 100):
    if db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    flt: Dict[str, Any] = {}
    if category:
        flt["category"] = category
    if q:
        flt["title"] = {"$regex": q, "$options": "i"}
    items = list(db.product.find(flt).limit(min(limit, 200)))
    return [serialize_doc(x) for x in items]


@app.get("/api/products/{product_id}")
def get_product(product_id: str):
    if db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    try:
        obj = db.product.find_one({"_id": ObjectId(product_id)})
    except Exception:
        obj = None
    if not obj:
        raise HTTPException(status_code=404, detail="Product not found")
    return serialize_doc(obj)


@app.post("/api/products")
def create_product(payload: ProductIn):
    # open (no auth) for MVP
    prod_id = create_document("product", payload.model_dump())
    obj = db.product.find_one({"_id": ObjectId(prod_id)})
    return serialize_doc(obj)


@app.post("/api/orders")
def create_order(payload: OrderIn):
    order_id = create_document("order", payload.model_dump())
    obj = db.order.find_one({"_id": ObjectId(order_id)})
    return serialize_doc(obj)


@app.get("/test")
def test_database():
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": None,
        "database_name": None,
        "connection_status": "Not Connected",
        "collections": []
    }
    try:
        if db is not None:
            response["database"] = "✅ Available"
            response["database_url"] = "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set"
            response["database_name"] = os.getenv("DATABASE_NAME") or "❌ Not Set"
            try:
                cols = db.list_collection_names()
                response["collections"] = cols
                response["database"] = "✅ Connected & Working"
                response["connection_status"] = "Connected"
            except Exception as e:
                response["database"] = f"⚠️ Connected but error: {str(e)[:80]}"
        else:
            response["database"] = "❌ Database not initialized"
    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:80]}"
    return response


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
