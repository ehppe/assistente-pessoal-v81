import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Window

ApplicationWindow {
    id: win
    width: 1200; height: 800; minimumWidth: 680; minimumHeight: 520
    visible: true; title: (d.nomeAssistente||"Neymar")+" 81 · Central"
    color: "#03070d"
    property var d: ponte.dados
    property bool conversa: false
    property color cyan: "#62e8ec"
    property bool ativo: visible && visibility !== Window.Minimized
    function nomeExibido() { return String(d.nomeAssistente||"Neymar").toUpperCase() }
    function nomeEspacado() { return nomeExibido().split("").join(" ") }
    onClosing: function(close) { close.accepted=false; hide() }
    onAtivoChanged: ponte.acao("visivel", ativo ? "true" : "false")
    Shortcut { sequence: "Escape"; onActivated: ponte.acao("parar","") }
    Connections {
        target: ponte
        function onMostrar() { win.showNormal(); win.raise(); win.requestActivate() }
    }
    Preferencias { id: preferencias; parent: Overlay.overlay }
    function previewConfig() { preferencias.jogo=false; preferencias.open() }
    function previewGame() { preferencias.jogo=true; preferencias.open() }
    function valor(k, unidade) {
        var n=(d.sensor || {})[k]
        return n === null || n === undefined ? "—" : Number(n).toFixed(0)+unidade
    }
    component Botao: Button {
        id: b
        property bool destaque: false
        font.pixelSize: 12
        leftPadding: 16; rightPadding: 16
        implicitHeight: 38
        contentItem: Text { text: b.text; color: b.destaque ? "#031619" : (b.hovered ? "#81fbff" : "#b4c5d0"); font: b.font; horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter }
        background: Rectangle { radius: 8; color: b.destaque ? (b.hovered ? "#94ffff" : "#62e8ec") : (b.hovered ? "#142732" : "#0b151e"); border.color: b.destaque ? "#62e8ec" : "#1a303e"; Behavior on color { ColorAnimation { duration: 140 } } }
    }
    header: Rectangle {
        height: 68; color: "#070e16"
        RowLayout {
            anchors.fill: parent; anchors.leftMargin: 22; anchors.rightMargin: 22; spacing: 8
            Text { text: "N /"; color: win.cyan; font.pixelSize: 24; font.bold: true; Layout.rightMargin: 16 }
            Botao { text: "Central"; destaque: !win.conversa; onClicked: win.conversa=false }
            Botao { text: "Conversa"; destaque: win.conversa; onClicked: win.conversa=true }
            Botao { text: "Nova conversa"; onClicked: ponte.acao("nova","") }
            Botao { text: "Configurações"; onClicked: { preferencias.jogo=false; preferencias.open() } }
            Botao { text: "Modo de jogo"; onClicked: { preferencias.jogo=true; preferencias.open() } }
            Item { Layout.fillWidth: true }
            Text { visible: win.width>1000; text: "CENTRAL PESSOAL  /  81"; color: "#68818f"; font.pixelSize: 10; font.letterSpacing: 2 }
        }
        Rectangle { anchors.bottom: parent.bottom; width: parent.width; height: 1; color: "#17313e" }
    }
    ColumnLayout {
        anchors.fill: parent; anchors.margins: 24; spacing: 14
        RowLayout {
            Layout.fillWidth: true
            Rectangle { width: 7; height: 7; radius: 4; color: win.cyan }
            Text { text: (d.estado || "Conectando").toUpperCase(); color: win.cyan; font.pixelSize: 11; font.letterSpacing: 2 }
            Text { text: d.jogo ? " / MODO DE JOGO" : " / CENTRAL ATIVA"; color: "#5c788a"; font.pixelSize: 10; font.letterSpacing: 1 }
            Item { Layout.fillWidth: true }
            Text { id: relogio; color: "#a9c4d3"; font.pixelSize: 12; text: Qt.formatDateTime(new Date(),"dd MMM yyyy  ·  HH:mm") }
            Timer { interval: 1000; repeat: true; running: win.ativo; onTriggered: relogio.text=Qt.formatDateTime(new Date(),"dd MMM yyyy  ·  HH:mm") }
        }
        Item {
            Layout.fillWidth: true; Layout.fillHeight: true
            visible: !win.conversa
            Rectangle { anchors.fill: parent; radius: 18; color: "#050d16"; border.color: "#142d3c" }
            Canvas {
                id: holo
                anchors.fill: parent
                property real fase: 0
                onPaint: {
                    var c=getContext("2d"), w=width, h=height, x=w/2, y=h*.48;
                    c.clearRect(0,0,w,h);
                    var r=Math.min(w*.22,h*.32), t=fase, speaking=d.falando, ouvindo=d.estado==="Ouvindo";
                    var nivel=(ouvindo||speaking) ? (d.microfoneNivel||0) : 0;
                    var glow=c.createRadialGradient(x,y,0,x,y,r*2.1);
                    glow.addColorStop(0,"#0a3445");glow.addColorStop(.5,"#081e32");glow.addColorStop(1,"#050d16");
                    c.fillStyle=glow;c.fillRect(1,1,w-2,h-2);
                    c.fillStyle="#164053";
                    for(var i=0;i<85;i++){var px=(i*197+19)%w,py=(i*97+11)%h;c.fillRect(px,py,1,1)}
                    c.lineWidth=1;
                    for(var k=0;k<7;k++){
                        c.strokeStyle=k%2 ? "#205274" : "#164354";c.beginPath();
                        c.ellipse(x-r,y-r+k*r*.285,r*2,Math.max(2,r*.15));c.stroke();
                    }
                    for(k=0;k<8;k++){
                        var rw=Math.abs(Math.sin(t*.3+k*Math.PI/8))*r;
                        c.strokeStyle="#226075";c.beginPath();c.ellipse(x-rw,y-r,rw*2,r*2);c.stroke();
                    }
                    for(k=0;k<3;k++){
                        c.save();c.translate(x,y);c.rotate((k-1)*.22);
                        c.strokeStyle=k===1 ? "#327485" : "#213750";c.beginPath();
                        c.ellipse(-r*1.65,-r*.32,r*3.3,r*.64);c.stroke();
                        var a=t*(k%2 ? -.6 : .5)+k*2;
                        c.fillStyle=k===1 ? "#b993ff" : "#72e8f2";c.beginPath();
                        c.arc(Math.cos(a)*r*1.65,Math.sin(a)*r*.32,3,0,Math.PI*2);c.fill();c.restore();
                    }
                    for(k=0;k<3;k++){
                        c.strokeStyle=["#165772","#9c69d9","#64e4ec"][k];c.beginPath();
                        for(i=0;i<=180;i++){
                            var xx=w*i/180,env=Math.exp(-Math.pow((xx-x)/(w*.28),2)*3);
                            var amp=(speaking||ouvindo) ? 8+nivel*42 : 4;
                            var yy=y+Math.sin(i*.3+t*3+k)*Math.sin(i*.09+k)*amp*env;
                            if(i===0)c.moveTo(xx,yy);else c.lineTo(xx,yy);
                        }c.stroke();
                    }
                }
                Timer { interval: d.jogo ? 1000 : ((d.falando || d.estado==="Ouvindo") ? 33 : 90); running: win.ativo && !win.conversa; repeat: true; onTriggered: { if(!d.jogo) holo.fase+=.07; holo.requestPaint() } }
                onWidthChanged: requestPaint()
                onHeightChanged: requestPaint()
            }
            Column {
                anchors.centerIn: parent; width: parent.width; spacing: 10
                Text {
                    anchors.horizontalCenter: parent.horizontalCenter
                    width: Math.min(parent.width*.82, 760)
                    height: 52
                    text: win.nomeEspacado()
                    color: "#affcff"
                    font.pixelSize: 38; fontSizeMode: Text.Fit; minimumPixelSize: 14
                    font.letterSpacing: text.length>20 ? 2 : 5
                    font.bold: true; horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter
                    wrapMode: Text.NoWrap
                }
                Text { anchors.horizontalCenter: parent.horizontalCenter; text: d.falando ? "ESTOU RESPONDENDO" : "SEU ASSISTENTE PESSOAL"; color: "#719caf"; font.pixelSize: 9; font.letterSpacing: 3 }
            }
            Column { anchors.left: parent.left; anchors.top: parent.top; anchors.margins: 22; spacing: 8
                Text { text: "NÚCLEO DE INTELIGÊNCIA"; color: "#7292a4"; font.pixelSize: 9; font.letterSpacing: 2 }
                Text { text: (d.provedor || "—").toUpperCase(); color: "#ddf4fa"; font.pixelSize: 15 }
            }
            Column { anchors.right: parent.right; anchors.top: parent.top; anchors.margins: 22; spacing: 8
                Text { text: "SAÍDA DE VOZ"; color: "#7292a4"; font.pixelSize: 9; font.letterSpacing: 2 }
                Text { text: (d.voz || "—").toUpperCase(); color: "#c2a1ee"; font.pixelSize: 15 }
            }
            Text { anchors.bottom: parent.bottom; anchors.horizontalCenter: parent.horizontalCenter; anchors.bottomMargin: 20; width: parent.width-50; horizontalAlignment: Text.AlignHCenter; text: d.status || "Conectando ao assistente…"; color: "#7995a7"; font.pixelSize: 11; elide: Text.ElideRight; textFormat: Text.PlainText }
        }
        RowLayout {
            visible: !win.conversa; Layout.fillWidth: true; spacing: 12
            Repeater {
                model: [{t:"PROCESSADOR",v:win.valor("cpu","%"),s:"Utilização atual"},
                        {t:"MEMÓRIA",v:win.valor("ram","%"),s:"RAM utilizada"},
                        {t:"ARMAZENAMENTO",v:win.valor("disco","%"),s:"Disco ocupado"}]
                Rectangle {
                    required property var modelData
                    Layout.fillWidth: true; Layout.preferredHeight: 106
                    radius: 12; color: "#0a141f"; border.color: "#19313f"
                    Column { anchors.fill: parent; anchors.margins: 15; spacing: 7
                        Text { text: modelData.t; color: "#7f9cad"; font.pixelSize: 9; font.letterSpacing: 1 }
                        Text { text: modelData.v; color: "#d1f7ff"; font.pixelSize: 26 }
                        Text { text: modelData.s; color: "#608296"; font.pixelSize: 10; width: parent.width; elide: Text.ElideRight }
                    }
                }
            }
            Repeater {
                model: [{t:"TEMPERATURA · CPU",chave:"temp_cpu",cor:"#ff6b6b",hist:"temp_cpu_historico"},
                        {t:"TEMPERATURA · GPU",chave:"temp_gpu",cor:"#ff9e4a",hist:"temp_gpu_historico"}]
                Rectangle {
                    id: cartaoTemp
                    required property var modelData
                    property var historico: (d.sensor||{})[modelData.hist] || []
                    property var fonteSensor: (d.sensor||{})[modelData.chave+"_fonte"] || ""
                    Layout.fillWidth: true; Layout.preferredHeight: 106
                    radius: 12; color: "#0a141f"; border.color: "#19313f"
                    RowLayout {
                        anchors.fill: parent; anchors.margins: 15; spacing: 10
                        Column {
                            Layout.preferredWidth: cartaoTemp.width*0.42; spacing: 7
                            Text { text: cartaoTemp.modelData.t; color: "#7f9cad"; font.pixelSize: 9; font.letterSpacing: 1 }
                            Text { text: win.valor(cartaoTemp.modelData.chave," °C"); color: "#d1f7ff"; font.pixelSize: 26 }
                            Text { text: cartaoTemp.fonteSensor || "Sensor indisponível"; color: "#608296"; font.pixelSize: 9; width: parent.width; wrapMode: Text.Wrap; maximumLineCount: 2; elide: Text.ElideRight }
                        }
                        Canvas {
                            id: grafico
                            Layout.fillWidth: true; Layout.fillHeight: true
                            property var pontos: cartaoTemp.historico
                            onPontosChanged: requestPaint()
                            onPaint: {
                                var c=getContext("2d"), w=width, h=height;
                                c.clearRect(0,0,w,h);
                                var p=pontos;
                                if(!p || p.length<2){
                                    c.fillStyle="#3a5568"; c.font="10px sans-serif"; c.fillText("Coletando histórico…",2,h/2);
                                    return;
                                }
                                var min=Math.min.apply(null,p), max=Math.max.apply(null,p);
                                if(max-min<2){min-=1;max+=1}
                                c.strokeStyle=cartaoTemp.modelData.cor; c.lineWidth=2; c.beginPath();
                                for(var i=0;i<p.length;i++){
                                    var x=w*i/(p.length-1), y=h-((p[i]-min)/(max-min))*h*0.85-h*0.05;
                                    if(i===0)c.moveTo(x,y);else c.lineTo(x,y);
                                }
                                c.stroke();
                            }
                        }
                    }
                }
            }
        }
        Rectangle {
            visible: win.conversa; Layout.fillWidth: true; Layout.fillHeight: true
            color: "#080f19"; radius: 14; border.color: "#1a303d"
            ColumnLayout {
                anchors.fill: parent; anchors.margins: 18; spacing: 14
                Text { text: "CONVERSA"; color: win.cyan; font.pixelSize: 12; font.letterSpacing: 2 }
                ScrollView {
                    id: scroll; Layout.fillWidth: true; Layout.fillHeight: true; clip: true
                    contentWidth: availableWidth
                    Column { width: scroll.availableWidth; spacing: 20
                        Text { visible: !(d.historico||[]).length; text: "O que vamos fazer hoje"+(d.nomeUsuario ? ", "+d.nomeUsuario : "")+"?"; color: "#a9c0cf"; font.pixelSize: 18 }
                        Repeater {
                            model: d.historico || []
                            Column {
                                required property var modelData
                                width: parent.width; spacing: 9
                                Text { text: "VOCÊ"; color: "#8a9dab"; font.pixelSize: 10 }
                                Text { width: parent.width; text: modelData.comando || ""; wrapMode: Text.Wrap; color: "#c4d8e3"; font.pixelSize: 14; textFormat: Text.PlainText }
                                Text { text: win.nomeExibido(); color: win.cyan; font.pixelSize: 10 }
                                Text { width: parent.width; text: modelData.resposta || ""; wrapMode: Text.Wrap; color: "#e1eff5"; font.pixelSize: 14; textFormat: Text.PlainText }
                            }
                        }
                    }
                }
                RowLayout {
                    Layout.fillWidth: true
                    TextField {
                        id: pedido; Layout.fillWidth: true; placeholderText: "Digite seu pedido…"; color: "#e1f6ff"; selectByMouse: true
                        background: Rectangle { radius: 8; color: "#101f2c"; border.color: pedido.activeFocus ? win.cyan : "#233847" }
                        onAccepted: enviar()
                        function enviar() { if(text.trim()) { ponte.acao("enviar",text); text="" } }
                    }
                    Botao { text: "Enviar"; destaque: true; onClicked: pedido.enviar() }
                }
            }
        }
        RowLayout {
            visible: !!(d.proposta||{}).token || !!d.energia
            Layout.fillWidth: true
            Text { Layout.fillWidth: true; text: d.energia ? "Confirmar ação de energia?" : "Confirmar lembrete: "+((d.proposta||{}).titulo||""); color: "#ffcd86"; elide: Text.ElideRight; textFormat: Text.PlainText }
            Botao { text: "Confirmar"; onClicked: ponte.acao(d.energia ? "energia" : "confirmar",JSON.stringify(d.energia ? d.tokenEnergia : d.proposta.token)) }
            Botao { text: "Cancelar"; onClicked: ponte.acao("cancelar","") }
        }
        RowLayout {
            Layout.fillWidth: true
            Botao { text: "●  Falar com "+(d.nomeAssistente||"Neymar"); destaque: true; onClicked: ponte.acao("ouvir","") }
            Botao { text: "Parar fala · Esc"; onClicked: ponte.acao("parar","") }
            Item { Layout.fillWidth: true }
            Text { visible: win.width>950; text: d.jogo ? "ANIMAÇÃO PAUSADA PARA JOGAR" : "CONEXÃO LOCAL COM O ASSISTENTE"; color: "#526f80"; font.pixelSize: 9; font.letterSpacing: 1 }
            Botao { text: "Tela clássica"; onClicked: ponte.acao("classica","") }
        }
    }
}
