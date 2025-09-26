"""Example FastAPI application with Radar integration."""

from typing import List, Optional
from datetime import datetime
from fastapi import FastAPI, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Boolean
try:
    from sqlalchemy.orm import declarative_base
except ImportError:
    from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session

from fastapi_radar import Radar

# Database setup
engine = create_engine(
    "sqlite:///./example.db", connect_args={"check_same_thread": False}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Models


class Product(Base):
    __tablename__ = "products"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False, index=True)
    description = Column(String(500))
    price = Column(Float, nullable=False)
    in_stock = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    email = Column(String(100), unique=True, nullable=False)
    full_name = Column(String(100))
    created_at = Column(DateTime, default=datetime.utcnow)


# Create tables
Base.metadata.create_all(bind=engine)

# Pydantic models


class ProductCreate(BaseModel):
    name: str
    description: Optional[str] = None
    price: float
    in_stock: bool = True


class ProductResponse(BaseModel):
    id: int
    name: str
    description: Optional[str]
    price: float
    in_stock: bool
    created_at: datetime

    class Config:
        from_attributes = True


class UserCreate(BaseModel):
    username: str
    email: str
    full_name: Optional[str] = None


class UserResponse(BaseModel):
    id: int
    username: str
    email: str
    full_name: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


# FastAPI app
app = FastAPI(
    title="Example App with Radar",
    description="Demonstration of FastAPI Radar debugging dashboard",
    version="1.0.0",
)

# Initialize Radar - automatically adds middleware and mounts dashboard
radar = Radar(
    app,
    db_engine=engine,
    dashboard_path="/__radar",
    slow_query_threshold=50,
    theme="auto",
)
radar.create_tables()

# Dependency


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# Routes


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": "Welcome to the Example API",
        "dashboard": "Visit /__radar to see the debugging dashboard",
    }


@app.get("/products", response_model=List[ProductResponse])
async def list_products(
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100),
    in_stock_only: bool = False,
    db: Session = Depends(get_db),
):
    """List all products with pagination."""
    query = db.query(Product)

    if in_stock_only:
        query = query.filter(Product.in_stock is True)

    products = query.offset(skip).limit(limit).all()
    return products


@app.get("/products/{product_id}", response_model=ProductResponse)
async def get_product(product_id: int, db: Session = Depends(get_db)):
    """Get a specific product by ID."""
    product = db.query(Product).filter(Product.id == product_id).first()

    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    return product


@app.post("/products", response_model=ProductResponse, status_code=201)
async def create_product(product: ProductCreate, db: Session = Depends(get_db)):
    """Create a new product."""
    db_product = Product(**product.dict())
    db.add(db_product)
    db.commit()
    db.refresh(db_product)
    return db_product


@app.put("/products/{product_id}", response_model=ProductResponse)
async def update_product(
    product_id: int, product: ProductCreate, db: Session = Depends(get_db)
):
    """Update an existing product."""
    db_product = db.query(Product).filter(Product.id == product_id).first()

    if not db_product:
        raise HTTPException(status_code=404, detail="Product not found")

    for key, value in product.dict().items():
        setattr(db_product, key, value)

    db.commit()
    db.refresh(db_product)
    return db_product


@app.delete("/products/{product_id}")
async def delete_product(product_id: int, db: Session = Depends(get_db)):
    """Delete a product."""
    db_product = db.query(Product).filter(Product.id == product_id).first()

    if not db_product:
        raise HTTPException(status_code=404, detail="Product not found")

    db.delete(db_product)
    db.commit()
    return {"message": "Product deleted successfully"}


@app.get("/users", response_model=List[UserResponse])
async def list_users(
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """List all users with pagination."""
    users = db.query(User).offset(skip).limit(limit).all()
    return users


@app.get("/users/{user_id}", response_model=UserResponse)
async def get_user(user_id: int, db: Session = Depends(get_db)):
    """Get a specific user by ID."""
    user = db.query(User).filter(User.id == user_id).first()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return user


@app.post("/users", response_model=UserResponse, status_code=201)
async def create_user(user: UserCreate, db: Session = Depends(get_db)):
    """Create a new user."""
    # Check for existing user
    existing_user = (
        db.query(User)
        .filter((User.username == user.username) | (User.email == user.email))
        .first()
    )

    if existing_user:
        raise HTTPException(
            status_code=400, detail="User with this username or email already exists"
        )

    db_user = User(**user.dict())
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user


@app.get("/slow-query")
async def slow_query_example(db: Session = Depends(get_db)):
    """Example endpoint that performs a slow query."""
    # This query will be highlighted as slow in Radar
    import time

    # Simulate a slow query
    products = db.query(Product).all()
    time.sleep(0.2)  # Simulate slow processing

    # Multiple queries to show query count
    for product in products[:3]:
        _ = db.query(User).filter(User.id == 1).first()

    return {
        "message": "This endpoint performs slow queries",
        "product_count": len(products),
    }


@app.get("/error")
async def trigger_error():
    """Example endpoint that raises an exception."""
    # This will be captured in the Exceptions tab
    raise ValueError("This is an example error for demonstration purposes")


@app.get("/health")
async def health_check():
    """Health check endpoint (excluded from Radar by default)."""
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn
    from pathlib import Path

    # Check if dashboard is built
    dashboard_dist = Path(__file__).parent / "fastapi_radar" / "dashboard" / "dist"
    if not dashboard_dist.exists():
        print("\n" + "=" * 60)
        print("⚠️  Dashboard not built yet!")
        print("=" * 60)
        print("\nPlease build the dashboard first:")
        print("  cd fastapi_radar/dashboard")
        print("  npm install")
        print("  npm run build")
        print("=" * 60 + "\n")

    # Add some sample data
    with SessionLocal() as db:
        if db.query(Product).count() == 0:
            sample_products = [
                Product(
                    name="Laptop",
                    description="High-performance laptop",
                    price=999.99,
                    in_stock=True,
                ),
                Product(
                    name="Mouse",
                    description="Wireless mouse",
                    price=29.99,
                    in_stock=True,
                ),
                Product(
                    name="Keyboard",
                    description="Mechanical keyboard",
                    price=149.99,
                    in_stock=False,
                ),
                Product(
                    name="Monitor",
                    description="4K display",
                    price=499.99,
                    in_stock=True,
                ),
                Product(
                    name="Headphones",
                    description="Noise-cancelling",
                    price=199.99,
                    in_stock=True,
                ),
            ]
            db.bulk_save_objects(sample_products)

            sample_users = [
                User(
                    username="johndoe", email="john@example.com", full_name="John Doe"
                ),
                User(
                    username="janedoe", email="jane@example.com", full_name="Jane Doe"
                ),
                User(
                    username="admin", email="admin@example.com", full_name="Admin User"
                ),
            ]
            db.bulk_save_objects(sample_users)
            db.commit()
            print("Sample data added to database")

    print("\n" + "=" * 60)
    print("🚀 FastAPI Radar Example App")
    print("=" * 60)
    print("\nEndpoints:")
    print("  API:       http://localhost:8000")
    print("  Docs:      http://localhost:8000/docs")
    print("  Dashboard: http://localhost:8000/__radar")
    print("\nTry these actions to see data in Radar:")
    print("  1. Visit http://localhost:8000/products")
    print("  2. Visit http://localhost:8000/slow-query")
    print("  3. Visit http://localhost:8000/error")
    print("=" * 60 + "\n")

    uvicorn.run(app, host="0.0.0.0", port=8000)
