"""Domain exceptions for Supermarket Ops Agent."""


class AppError(Exception):
    """Base application exception."""
    def __init__(self, message: str, details: dict | None = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}


class ProductNotFoundError(AppError):
    """Raised when a queried product cannot be found."""
    def __init__(self, query: str):
        super().__init__(f"Product not found matching: '{query}'", {"query": query})


class InsufficientStockError(AppError):
    """Raised when stock decrement would violate oversell constraints."""
    def __init__(self, product_name: str, requested: float, available: float):
        super().__init__(
            f"Insufficient stock for '{product_name}'. Requested: {requested}, Available: {available}",
            {"product_name": product_name, "requested": requested, "available": available}
        )


class BelowCostError(AppError):
    """Raised when selling price is lower than cost price without explicit override."""
    def __init__(self, product_name: str, cost_price: float, selling_price: float):
        super().__init__(
            f"Selling price (₹{selling_price:.2f}) is below cost price (₹{cost_price:.2f}) for '{product_name}'. "
            "Confirmation required to sell below cost.",
            {"product_name": product_name, "cost_price": cost_price, "selling_price": selling_price}
        )


class CustomerNotFoundError(AppError):
    """Raised when a khata customer cannot be found."""
    def __init__(self, customer_name: str):
        super().__init__(
            f"Customer '{customer_name}' not found in Khata ledger.",
            {"customer_name": customer_name}
        )


class BillNotFoundError(AppError):
    """Raised when a referenced bill does not exist."""
    def __init__(self, bill_id: int):
        super().__init__(f"Bill #{bill_id} not found.", {"bill_id": bill_id})


class BillAlreadyFinalizedError(AppError):
    """Raised when attempting to modify or re-finalize a finalized bill."""
    def __init__(self, bill_id: int):
        super().__init__(
            f"Bill #{bill_id} is already finalized and cannot be modified or re-finalized.",
            {"bill_id": bill_id}
        )


class BillCancelledError(AppError):
    """Raised when attempting an operation on a cancelled bill."""
    def __init__(self, bill_id: int):
        super().__init__(
            f"Bill #{bill_id} has been cancelled.",
            {"bill_id": bill_id}
        )


class EmptyBillError(AppError):
    """Raised when attempting to finalize a bill with no line items."""
    def __init__(self, bill_id: int):
        super().__init__(
            f"Bill #{bill_id} has no items. Add items before finalizing.",
            {"bill_id": bill_id}
        )


class DuplicateUpdateError(AppError):
    """Raised when an update_id has already been processed (idempotency guard)."""
    def __init__(self, update_id: int):
        super().__init__(
            f"Telegram update #{update_id} has already been processed.",
            {"update_id": update_id}
        )


class InvalidOperationError(AppError):
    """Raised for general invalid domain operations."""
    pass
