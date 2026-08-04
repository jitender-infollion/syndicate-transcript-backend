import logging
from datetime import datetime, timedelta

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError

from apis.controllers.transcripts.transcripts_handler import _SLIM_COLUMNS, _row_to_list_item
from apis.models.author import Author
from apis.models.cart import Cart, CartItem, CartStatus
from apis.models.transcript import Transcript
from services.database.postgres.connection import get_session

from .cart_schema import CartResponse

logger = logging.getLogger(__name__)


def _get_cart(session, user_id: int | None, guest_id: str | None, *, create: bool) -> Cart | None:
    query = session.query(Cart).filter(Cart.status == CartStatus.ACTIVE.value)
    if user_id is not None:
        cart = query.filter(Cart.user_id == user_id).first()
    elif guest_id:
        cart = query.filter(Cart.guest_id == guest_id).first()
    else:
        cart = None

    if cart is None and create:
        cart = Cart(
            user_id=user_id,
            guest_id=guest_id if user_id is None else None,
            status=CartStatus.ACTIVE.value,
            expires_at=datetime.utcnow() + timedelta(days=180) if user_id is None else None,
        )
        session.add(cart)
        session.flush()
    return cart


def _cart_response(session, cart: Cart | None) -> CartResponse:
    if cart is None:
        return CartResponse(items=[])
    rows = (
        session.query(*_SLIM_COLUMNS)
        .join(Author, Transcript.author_id == Author.id)
        .join(CartItem, CartItem.transcript_id == Transcript.id)
        .filter(CartItem.cart_id == cart.id)
        .order_by(CartItem.created_at.desc())
        .all()
    )
    return CartResponse(items=[_row_to_list_item(row) for row in rows])


def handle_get_cart(user_id: int | None, guest_id: str | None) -> CartResponse:
    session = get_session()
    try:
        cart = _get_cart(session, user_id, guest_id, create=False)
        return _cart_response(session, cart)
    except Exception:
        logger.exception("Failed to fetch cart")
        raise HTTPException(status_code=500, detail="Internal error") from None
    finally:
        session.close()


def handle_add_item(user_id: int | None, guest_id: str | None, transcript_id: int) -> CartResponse:
    if user_id is None and not guest_id:
        raise HTTPException(status_code=400, detail="A guest cart identity is required.")

    session = get_session()
    try:
        transcript = (
            session.query(Transcript.id)
            .filter(Transcript.id == transcript_id, Transcript.is_active.is_(True))
            .first()
        )
        if not transcript:
            raise HTTPException(status_code=404, detail="Transcript not found")

        cart = _get_cart(session, user_id, guest_id, create=True)
        session.add(CartItem(cart_id=cart.id, transcript_id=transcript_id))
        try:
            session.commit()
        except IntegrityError:
            # Already in the cart - idempotent no-op, not an error.
            session.rollback()
        return _cart_response(session, cart)
    except HTTPException:
        session.rollback()
        raise
    except Exception:
        session.rollback()
        logger.exception("Failed to add cart item")
        raise HTTPException(status_code=500, detail="Internal error") from None
    finally:
        session.close()


def handle_remove_item(user_id: int | None, guest_id: str | None, transcript_id: int) -> CartResponse:
    session = get_session()
    try:
        cart = _get_cart(session, user_id, guest_id, create=False)
        if cart is not None:
            session.query(CartItem).filter(
                CartItem.cart_id == cart.id, CartItem.transcript_id == transcript_id
            ).delete()
            session.commit()
        return _cart_response(session, cart)
    except Exception:
        session.rollback()
        logger.exception("Failed to remove cart item")
        raise HTTPException(status_code=500, detail="Internal error") from None
    finally:
        session.close()


def handle_clear_cart(user_id: int | None, guest_id: str | None) -> CartResponse:
    session = get_session()
    try:
        cart = _get_cart(session, user_id, guest_id, create=False)
        if cart is not None:
            session.query(CartItem).filter(CartItem.cart_id == cart.id).delete()
            session.commit()
        return CartResponse(items=[])
    except Exception:
        session.rollback()
        logger.exception("Failed to clear cart")
        raise HTTPException(status_code=500, detail="Internal error") from None
    finally:
        session.close()


def handle_merge_cart(user_id: int, guest_id: str | None, item_ids: list[int]) -> CartResponse:
    session = get_session()
    try:
        user_cart = _get_cart(session, user_id, None, create=False)
        guest_cart = _get_cart(session, None, guest_id, create=False) if guest_id else None

        if user_cart is None and guest_cart is not None:
            # No cart of their own yet - re-point the guest cart at the user instead of
            # copying rows into a freshly created one (keeps this a single UPDATE).
            guest_cart.user_id = user_id
            guest_cart.guest_id = None
            guest_cart.expires_at = None
            user_cart = guest_cart
            guest_cart = None

        candidate_ids = set(item_ids or [])
        if guest_cart is not None:
            candidate_ids |= {
                row[0]
                for row in session.query(CartItem.transcript_id).filter(CartItem.cart_id == guest_cart.id).all()
            }

        if candidate_ids:
            if user_cart is None:
                user_cart = _get_cart(session, user_id, None, create=True)
            valid_ids = {
                row[0]
                for row in session.query(Transcript.id)
                .filter(Transcript.id.in_(candidate_ids), Transcript.is_active.is_(True))
                .all()
            }
            existing_ids = {
                row[0]
                for row in session.query(CartItem.transcript_id).filter(CartItem.cart_id == user_cart.id).all()
            }
            for transcript_id in valid_ids - existing_ids:
                session.add(CartItem(cart_id=user_cart.id, transcript_id=transcript_id))

        if guest_cart is not None:
            session.delete(guest_cart)

        session.commit()
        return _cart_response(session, user_cart) if user_cart is not None else CartResponse(items=[])
    except Exception:
        session.rollback()
        logger.exception("Failed to merge cart")
        raise HTTPException(status_code=500, detail="Internal error") from None
    finally:
        session.close()
