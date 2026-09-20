"""Atalho global Ctrl+Alt+Espaço para interromper a voz, sem capturar digitação."""
import sys
import threading

def iniciar(encerrar,interromper,registrar):
    if sys.platform!='win32':return
    def escutar():
        import ctypes
        from ctypes import wintypes
        user=ctypes.WinDLL('user32',use_last_error=True)
        user.RegisterHotKey.argtypes=[wintypes.HWND,ctypes.c_int,wintypes.UINT,wintypes.UINT]
        user.RegisterHotKey.restype=wintypes.BOOL
        user.UnregisterHotKey.argtypes=[wintypes.HWND,ctypes.c_int]
        user.PeekMessageW.argtypes=[ctypes.POINTER(wintypes.MSG),wintypes.HWND,wintypes.UINT,wintypes.UINT,wintypes.UINT]
        ident=0x4A54
        if not user.RegisterHotKey(None,ident,0x0001|0x0002|0x4000,0x20):
            registrar('Atalho Ctrl+Alt+Espaço indisponível. Use Parar fala na janela do Neymar.');return
        try:
            msg=wintypes.MSG()
            while not encerrar.is_set():
                while user.PeekMessageW(ctypes.byref(msg),None,0,0,1):
                    if msg.message==0x0312 and msg.wParam==ident:interromper()
                encerrar.wait(.05)
        finally:user.UnregisterHotKey(None,ident)
    threading.Thread(target=escutar,name='NeymarAtalhoFala',daemon=True).start()
