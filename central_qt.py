"""Interface Qt isolada. stdin/stdout são reservados à ponte local."""
import json
import os
from pathlib import Path
import sys
import threading
from PySide6.QtCore import QObject, Property, Signal, Slot, QUrl, QTimer
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuick import QQuickWindow

class Ponte(QObject):
    recebido=Signal(str)
    changed=Signal()
    mostrar=Signal()
    mostrarCompacto=Signal()
    ocultarCompacto=Signal()
    def __init__(self):
        super().__init__()
        self._dados={'estado':'Conectando','sensor':{},'historico':[],'proposta':{},'energia':False,'jogo':False,'falando':False}
        self.recebido.connect(self.aplicar)

    @Property('QVariantMap',notify=changed)
    def dados(self):return self._dados

    @Slot(str)
    def aplicar(self,linha):
        if linha=='__EOF__':QGuiApplication.exit(0);return
        try:
            dados=json.loads(linha)
            if not isinstance(dados,dict):return
            if dados!=self._dados:
                self._dados=dados;self.changed.emit()
            if dados.get('mostrar'):self.mostrar.emit()
            if dados.get('mostrarCompacto'):self.mostrarCompacto.emit()
            if dados.get('ocultarCompacto'):self.ocultarCompacto.emit()
        except ValueError:pass

    @Slot(str,str)
    def acao(self,nome,valor=''):
        e={'acao':nome}
        if nome in ('salvar_config','salvar_jogo','ativar_jogo'):
            try:e['dados']=json.loads(valor)
            except ValueError:return
        elif nome=='enviar':e['texto']=valor
        elif nome=='visivel':e['valor']=valor=='true'
        elif nome in ('confirmar','energia'):
            try:e['token']=json.loads(valor)
            except ValueError:return
        try:print(json.dumps(e,ensure_ascii=False),flush=True)
        except (OSError,ValueError):QGuiApplication.exit(0)

def main():
    for stream in (sys.stdin,sys.stdout):
        if stream is not None and hasattr(stream,"reconfigure"):
            stream.reconfigure(encoding="utf-8",errors="strict")
    app=QGuiApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    engine=QQmlApplicationEngine()
    ponte=Ponte()
    engine.rootContext().setContextProperty('ponte',ponte)
    engine.load(QUrl.fromLocalFile(str(Path(__file__).parent/'interface_qt'/'Main.qml')))
    engine.load(QUrl.fromLocalFile(str(Path(__file__).parent/'interface_qt'/'Compact.qml')))
    if not engine.rootObjects():return 2
    def ler():
        for linha in sys.stdin:
            ponte.recebido.emit(linha)
        ponte.recebido.emit('__EOF__')
    threading.Thread(target=ler,daemon=True).start()
    ponte.acao('pronto','')
    if '--config-preview' in sys.argv or '--game-preview' in sys.argv:
        from PySide6.QtCore import QMetaObject
        def abrir_preview():
            QMetaObject.invokeMethod(engine.rootObjects()[0],'previewGame' if '--game-preview' in sys.argv else 'previewConfig')
        QTimer.singleShot(600,abrir_preview)
    if '--compact-preview' in sys.argv:
        def abrir_compacto():
            raizes=engine.rootObjects()
            if len(raizes)>1:
                raizes[0].hide();raizes[1].show()
        QTimer.singleShot(200,abrir_compacto)
    if '--captura' in sys.argv:
        def captura():
            raizes=engine.rootObjects()
            indice=1 if '--compact-preview' in sys.argv and len(raizes)>1 else 0
            raizes[indice].grabWindow().save(str(Path(__file__).parent/'preview-qt.png'))
            app.exit(0)
        QTimer.singleShot(1800,captura)
    return app.exec()

if __name__=='__main__':sys.exit(main())
