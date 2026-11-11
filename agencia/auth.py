from functools import wraps
from django.contrib import messages
from django.shortcuts import redirect, render


def login_requerido(vista):
    @wraps(vista)
    def f(request, *a, **k):
        if not request.usuario:
            messages.warning(request, "Inicie sesión para continuar.")
            return redirect(f"/ingresar/?next={request.path}")
        return vista(request, *a, **k)
    return f


def permiso(*codigos):
    """Exige que el usuario tenga TODOS los permisos indicados (RBAC verificado contra la BD)."""
    def deco(vista):
        @wraps(vista)
        def f(request, *a, **k):
            if not request.usuario:
                messages.warning(request, "Inicie sesión para continuar.")
                return redirect(f"/ingresar/?next={request.path}")
            if not all(c in request.permisos for c in codigos):
                return render(request, "403.html", status=403)
            return vista(request, *a, **k)
        return f
    return deco


def solo_cliente(vista):
    @wraps(vista)
    def f(request, *a, **k):
        if not request.usuario:
            messages.warning(request, "Inicie sesión para continuar.")
            return redirect(f"/ingresar/?next={request.path}")
        if not request.cliente:
            return render(request, "403.html", status=403)
        return vista(request, *a, **k)
    return f
