"""Engine layer: cancellation, probing, choice construction, downloading.

This layer is deliberately Textual-free. Everything here is synchronous or
plain asyncio; Textual :class:`~textual.worker.Worker` wiring lives in
:mod:`siphon.workers`.
"""
