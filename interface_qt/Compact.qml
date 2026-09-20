import QtQuick
import QtQuick.Controls
import QtQuick.Window

Window {
    id: win
    width: 360; height: 390
    visible: false
    color: "transparent"
    flags: Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint
    title: (d.nomeAssistente || "Neymar") + " 81 · Compacto"
    property var d: ponte.dados
    property real fase: 0
    property color corEstado: d.estado === "Ouvindo" ? "#48f3ff"
                              : d.estado === "Pensando" || d.estado === "Transcrevendo" ? "#bd83ff"
                              : d.falando ? "#48ffb0"
                              : d.estado === "Pausado" ? "#778492" : "#62e8ec"
    function nomeExibido() { return String(d.nomeAssistente || "Neymar").toUpperCase() }
    function nomeEspacado() {
        var n=nomeExibido()
        return n.length <= 12 ? n.split("").join(" ") : n
    }
    function exibir() { show(); raise(); requestActivate() }
    onVisibleChanged: ponte.acao("compacto_visivel", visible ? "true" : "false")
    Connections {
        target: ponte
        function onMostrarCompacto() { win.exibir() }
        function onOcultarCompacto() { win.hide() }
    }

    Rectangle {
        id: painel
        anchors.fill: parent; anchors.margins: 7
        radius: 20; color: "#f7030b14"; border.color: "#23495b"; border.width: 1

        MouseArea {
            anchors.fill: parent
            onPressed: win.startSystemMove()
            onDoubleClicked: ponte.acao("ouvir", "")
        }

        Canvas {
            id: estrelas
            anchors.fill: parent
            onPaint: {
                var c=getContext("2d"), w=width, h=height
                c.clearRect(0,0,w,h); c.fillStyle="#23556b"
                for(var i=0;i<48;i++){
                    var x=(i*83+19)%w, y=(i*47+31)%h
                    c.globalAlpha=.25+(i%5)*.1; c.fillRect(x,y,i%11===0?2:1,i%11===0?2:1)
                }
                c.globalAlpha=1
            }
        }

        Row {
            anchors.left: parent.left; anchors.top: parent.top
            anchors.leftMargin: 18; anchors.topMargin: 14; spacing: 8
            Rectangle { width: 7; height: 7; radius: 4; color: win.corEstado; anchors.verticalCenter: parent.verticalCenter }
            Text { text: (d.estado || "CONECTANDO").toUpperCase(); color: win.corEstado; font.pixelSize: 9; font.letterSpacing: 1.5 }
        }
        Row {
            anchors.right: parent.right; anchors.top: parent.top
            anchors.rightMargin: 12; anchors.topMargin: 7; spacing: 2
            ToolButton {
                width: 34; height: 32; text: "□"
                onClicked: ponte.acao("mostrar_central", "")
                contentItem: Text { text: parent.text; color: parent.hovered ? "#affcff" : "#6f94a8"; horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter; font.pixelSize: 15 }
                background: Rectangle { radius: 8; color: parent.hovered ? "#122635" : "transparent" }
                ToolTip.visible: hovered; ToolTip.text: "Abrir Central"
            }
            ToolButton {
                width: 34; height: 32; text: "×"
                onClicked: win.hide()
                contentItem: Text { text: parent.text; color: parent.hovered ? "#ff9da8" : "#6f94a8"; horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter; font.pixelSize: 18 }
                background: Rectangle { radius: 8; color: parent.hovered ? "#2a1720" : "transparent" }
                ToolTip.visible: hovered; ToolTip.text: "Ocultar"
            }
        }

        Canvas {
            id: holo
            anchors.left: parent.left; anchors.right: parent.right
            anchors.top: parent.top; anchors.topMargin: 42
            height: 258
            onPaint: {
                var c=getContext("2d"), w=width, h=height, x=w/2, y=h*.47
                c.clearRect(0,0,w,h)
                var r=Math.min(w*.29,h*.40), nivel=(d.estado==="Ouvindo"||d.falando)?(d.microfoneNivel||0):0
                var glow=c.createRadialGradient(x,y,0,x,y,r*1.8)
                glow.addColorStop(0,"#16384a"); glow.addColorStop(.48,"#092135"); glow.addColorStop(1,"rgba(3,11,20,0)")
                c.fillStyle=glow; c.fillRect(0,0,w,h)
                c.lineWidth=1
                for(var k=0;k<7;k++){
                    c.strokeStyle=k===3 ? "#31758b" : "#1d5069"; c.beginPath()
                    c.ellipse(x-r,y-r+k*r*.333,r*2,Math.max(2,r*.14)); c.stroke()
                }
                for(k=0;k<8;k++){
                    var rw=Math.abs(Math.sin(fase*.32+k*Math.PI/8))*r
                    c.strokeStyle="#24627a"; c.beginPath(); c.ellipse(x-rw,y-r,rw*2,r*2); c.stroke()
                }
                for(k=0;k<3;k++){
                    c.save(); c.translate(x,y); c.rotate((k-1)*.23)
                    c.strokeStyle=k===1 ? "#3d8fa2" : "#273e5b"; c.beginPath(); c.ellipse(-r*1.68,-r*.30,r*3.36,r*.60); c.stroke()
                    var a=fase*(k%2?-.7:.55)+k*2
                    c.fillStyle=k===1 ? "#bd83ff" : "#70f1f5"; c.beginPath(); c.arc(Math.cos(a)*r*1.68,Math.sin(a)*r*.30,2.5,0,Math.PI*2); c.fill(); c.restore()
                }
                c.strokeStyle=win.corEstado; c.globalAlpha=.75; c.beginPath()
                for(var i=0;i<=150;i++){
                    var xx=w*i/150, env=Math.exp(-Math.pow((xx-x)/(w*.32),2)*3)
                    var amp=(d.falando||d.estado==="Ouvindo") ? 5+nivel*24 : 2
                    var yy=y+Math.sin(i*.31+fase*3)*Math.sin(i*.09)*amp*env
                    if(i===0)c.moveTo(xx,yy);else c.lineTo(xx,yy)
                }
                c.stroke(); c.globalAlpha=1
            }
            Timer { interval: d.jogo ? 800 : ((d.falando || d.estado==="Ouvindo") ? 33 : 80); running: win.visible; repeat: true; onTriggered: { if(!d.jogo) win.fase+=.07; holo.requestPaint() } }
            onWidthChanged: requestPaint(); onHeightChanged: requestPaint()
        }

        Rectangle { anchors.left: parent.left; anchors.right: parent.right; anchors.verticalCenter: holo.verticalCenter; height: 1; color: win.corEstado; opacity: .72 }
        Column {
            anchors.horizontalCenter: parent.horizontalCenter; y: 137
            width: parent.width-32; spacing: 6
            Text {
                width: parent.width; height: 44; text: win.nomeEspacado(); color: "#d9fcff"
                font.pixelSize: 29; fontSizeMode: Text.Fit; minimumPixelSize: 12
                font.letterSpacing: text.length>20 ? 1.5 : 4; font.bold: true
                horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter
            }
            Text { anchors.horizontalCenter: parent.horizontalCenter; text: d.falando ? "ESTOU RESPONDENDO" : "SEU ASSISTENTE PESSOAL"; color: "#6395a9"; font.pixelSize: 8; font.letterSpacing: 2.4 }
        }

        Rectangle {
            anchors.left: parent.left; anchors.right: parent.right; anchors.bottom: parent.bottom
            anchors.margins: 14; height: 58; radius: 12; color: "#0a1826"; border.color: "#193a4b"
            Rectangle { width: 4; height: 24; radius: 2; color: win.corEstado; anchors.left: parent.left; anchors.leftMargin: 12; anchors.verticalCenter: parent.verticalCenter }
            Text { anchors.left: parent.left; anchors.right: parent.right; anchors.leftMargin: 27; anchors.rightMargin: 54; anchors.verticalCenter: parent.verticalCenter; text: d.status || "Pronto."; color: "#a8c7d4"; font.pixelSize: 11; wrapMode: Text.Wrap; maximumLineCount: 2; elide: Text.ElideRight }
            ToolButton {
                anchors.right: parent.right; anchors.rightMargin: 9; anchors.verticalCenter: parent.verticalCenter
                width: 38; height: 38; text: "●"; onClicked: ponte.acao("ouvir", "")
                contentItem: Text { text: parent.text; color: win.corEstado; horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter; font.pixelSize: 17 }
                background: Rectangle { radius: 19; color: "#102638"; border.color: win.corEstado }
                ToolTip.visible: hovered; ToolTip.text: "Falar com " + (d.nomeAssistente || "Neymar")
            }
        }
    }
}
