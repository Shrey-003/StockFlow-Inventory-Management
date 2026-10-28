import logging
from collections.abc import Generator
from datetime import datetime, timedelta, timezone

from fastapi import Depends, FastAPI, HTTPException, Query, Response, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func, select, text, update
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from database import SessionLocal, engine
from models import Product, Reservation
from schemas import (
    ProductRead,
    ProductUpdate,
    ProductWrite,
    ReservationCreate,
    ReservationRead,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="StockFlow API",
    description="Inventory and Order Management Platform",
    version="0.1.0",
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:4200",
        "http://127.0.0.1:4200",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def commit_changes(db: Session) -> None:
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The operation conflicts with existing data. "
                   "Check that the SKU is unique.",
        ) from exc
    except SQLAlchemyError as exc:
        db.rollback()
        logger.exception("Database operation failed")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="The database operation could not be completed.",
        ) from exc


@app.get("/health", tags=["Health"])
def health_check() -> dict[str, str]:
    return {
        "status": "ok",
        "service": "stockflow-api",
    }


@app.get("/health/db", tags=["Health"])
def database_health_check() -> dict[str, str]:
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))

        return {
            "status": "ok",
            "database": "connected",
        }
    except SQLAlchemyError as exc:
        logger.exception("Database health check failed")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database connection unavailable",
        ) from exc


@app.post(
    "/products",
    response_model=ProductRead,
    status_code=status.HTTP_201_CREATED,
    tags=["Products"],
)
def create_product(
    payload: ProductWrite,
    db: Session = Depends(get_db),
) -> Product:
    product = Product(**payload.model_dump())
    db.add(product)
    commit_changes(db)
    db.refresh(product)
    return product


@app.get(
    "/products",
    response_model=list[ProductRead],
    tags=["Products"],
)
def list_products(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
    db: Session = Depends(get_db),
) -> list[Product]:
    return (
        db.query(Product)
        .order_by(Product.id)
        .offset(skip)
        .limit(limit)
        .all()
    )


@app.get(
    "/products/{product_id}",
    response_model=ProductRead,
    tags=["Products"],
)
def get_product(
    product_id: int,
    db: Session = Depends(get_db),
) -> Product:
    product = db.get(Product, product_id)

    if product is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found.",
        )

    return product


@app.patch(
    "/products/{product_id}",
    response_model=ProductRead,
    tags=["Products"],
)
def update_product(
    product_id: int,
    payload: ProductUpdate,
    db: Session = Depends(get_db),
) -> Product:
    product = db.get(Product, product_id)

    if product is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found.",
        )

    changes = payload.model_dump(exclude_unset=True)

    for field, value in changes.items():
        setattr(product, field, value)

    commit_changes(db)
    db.refresh(product)
    return product


@app.delete(
    "/products/{product_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["Products"],
)
def delete_product(
    product_id: int,
    db: Session = Depends(get_db),
) -> Response:
    product = db.get(Product, product_id)

    if product is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found.",
        )

    db.delete(product)
    commit_changes(db)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@app.post(
    "/products/{product_id}/reservations",
    response_model=ReservationRead,
    status_code=status.HTTP_201_CREATED,
    tags=["Reservations"],
)
def reserve_inventory(
    product_id: int,
    payload: ReservationCreate,
    db: Session = Depends(get_db),
) -> Reservation:
    try:
        with db.begin():
            # Atomically reduce stock only if enough stock remains.
            result = db.execute(
                update(Product)
                .where(
                    Product.id == product_id,
                    Product.stock_quantity >= payload.quantity,
                )
                .values(
                    stock_quantity=Product.stock_quantity - payload.quantity,
                    updated_at=func.now(),
                )
                .returning(Product.id)
            )

            reserved_product_id = result.scalar_one_or_none()

            if reserved_product_id is None:
                product_exists = db.scalar(
                    select(Product.id).where(Product.id == product_id)
                )

                if product_exists is None:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail="Product not found.",
                    )

                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Insufficient stock available.",
                )

            reservation = Reservation(
                product_id=product_id,
                quantity=payload.quantity,
                status="active",
                expires_at=(
                    datetime.now(timezone.utc)
                    + timedelta(minutes=payload.ttl_minutes)
                ),
            )

            db.add(reservation)
            db.flush()
            db.refresh(reservation)

        return reservation

    except HTTPException:
        raise
    except SQLAlchemyError as exc:
        logger.exception("Inventory reservation failed")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Could not complete inventory reservation.",
        ) from exc

@app.post(
    "/reservations/{reservation_id}/cancel",
    response_model=ReservationRead,
    tags=["Reservations"],
)
def cancel_reservation(
    reservation_id: int,
    db: Session = Depends(get_db),
) -> Reservation:
    try:
        with db.begin():
            # Lock this reservation to prevent concurrent cancellation.
            reservation = db.scalar(
                select(Reservation)
                .where(Reservation.id == reservation_id)
                .with_for_update()
            )

            if reservation is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Reservation not found.",
                )

            if reservation.status != "active":
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Reservation is no longer active.",
                )

            # Restore inventory and change reservation status
            # in the same transaction.
            db.execute(
                update(Product)
                .where(Product.id == reservation.product_id)
                .values(
                    stock_quantity=(
                        Product.stock_quantity + reservation.quantity
                    ),
                    updated_at=func.now(),
                )
            )

            now = datetime.now(timezone.utc)
            reservation.status = (
                "expired"
                if reservation.expires_at <= now
                else "cancelled"
            )

            db.flush()
            db.refresh(reservation)

        return reservation

    except SQLAlchemyError as exc:
        logger.exception("Reservation cancellation failed")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Could not cancel the reservation.",
        ) from exc

@app.get(
    "/reservations",
    response_model=list[ReservationRead],
    tags=["Reservations"],
)
def list_reservations(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
    db: Session = Depends(get_db),
) -> list[Reservation]:
    return db.scalars(
        select(Reservation)
        .order_by(
            Reservation.created_at.desc(),
            Reservation.id.desc(),
        )
        .offset(skip)
        .limit(limit)
    ).all()


@app.get(
    "/reservations/{reservation_id}",
    response_model=ReservationRead,
    tags=["Reservations"],
)
def get_reservation(
    reservation_id: int,
    db: Session = Depends(get_db),
) -> Reservation:
    reservation = db.get(Reservation, reservation_id)

    if reservation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Reservation not found.",
        )

    return reservation


@app.post(
    "/reservations/expire-due",
    tags=["Reservations"],
)
def expire_due_reservations(
    db: Session = Depends(get_db),
) -> dict[str, int]:
    expired_count = 0

    try:
        with db.begin():
            now = datetime.now(timezone.utc)

            due_reservations = db.scalars(
                select(Reservation)
                .where(
                    Reservation.status == "active",
                    Reservation.expires_at <= now,
                )
                .order_by(Reservation.id)
                .limit(100)
                .with_for_update(skip_locked=True)
            ).all()

            for reservation in due_reservations:
                db.execute(
                    update(Product)
                    .where(Product.id == reservation.product_id)
                    .values(
                        stock_quantity=(
                            Product.stock_quantity + reservation.quantity
                        ),
                        updated_at=func.now(),
                    )
                )

                reservation.status = "expired"
                expired_count += 1

        return {"expired_count": expired_count}

    except SQLAlchemyError as exc:
        logger.exception("Expired reservation processing failed")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Could not process expired reservations.",
        ) from exc
