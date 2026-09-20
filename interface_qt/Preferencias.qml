import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
Popup {
    id: p
    objectName: "preferencias"
    property bool jogo: false
    property var campos: []
    property var rascunho: ({})
    property var programas: []
    property var selecionados: ({})
    property bool alto: false
    property bool gamebar: false
    property bool indexacao: false
    property int aba: 0
    property int versao: -1
    anchors.centerIn: parent
    width: Math.min(parent.width-28,850)
    height: Math.min(parent.height-28,680)
    modal: true; closePolicy: Popup.CloseOnEscape
    padding: 22
    background: Rectangle { color: "#09131e"; radius: 16; border.color: "#295064" }
    function atualizar() {
        var d=ponte.dados, vals={}, checks={};
        campos=(d.preferencias||{}).campos||[];
        for(var i=0;i<campos.length;i++) vals[campos[i].chave]=campos[i].valor;
        rascunho=vals;
        var j=d.jogoOpcoes||{};
        programas=j.programas||[];
        (j.selecionados||[]).forEach(function(n){checks[n]=true});
        selecionados=checks;alto=!!j.alto;gamebar=!!j.gamebar;indexacao=!!j.indexacao;
        versao=d.revisao||0;
    }
    function salvar(ativar) {
        if(!jogo) { ponte.acao("salvar_config",JSON.stringify(rascunho)); return }
        var lista=[];
        for(var n in selecionados) if(selecionados[n])lista.push(n);
        ponte.acao(ativar ? "ativar_jogo" : "salvar_jogo",JSON.stringify({programas:lista,alto:alto,gamebar:gamebar,indexacao:indexacao}));
    }
    onOpened: { atualizar(); ponte.acao("recarregar_config","") }
    Connections { target: ponte
        function onChanged() { if(p.visible && ponte.dados.revisao!==p.versao)p.atualizar() }
    }
    component Acao: Button {
        id: b
        implicitHeight: 38
        contentItem: Text { text:b.text; color:"#c9f7ff"; horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter }
        background: Rectangle { radius:7; color:b.hovered ? "#234658" : "#152d3d"; border.color:"#2c576c" }
    }
    ColumnLayout {
        anchors.fill: parent; spacing: 14
        RowLayout {
            Layout.fillWidth: true
            Text { text:p.jogo ? "MODO DE JOGO" : "CONFIGURAÇÕES"; color:"#6ce9eb"; font.pixelSize:19; font.letterSpacing:2 }
            Item { Layout.fillWidth:true }
            Acao { text:"Fechar"; onClicked:p.close() }
        }
        RowLayout {
            visible:!p.jogo; Layout.fillWidth:true
            Repeater {
                model:["Inteligência","Voz","Microfone","Sistema"]
                Acao { required property int index; required property string modelData
                    text:(p.aba===index ? "● " : "")+modelData
                    Layout.fillWidth:true
                    onClicked:p.aba=index
                }
            }
        }
        ScrollView {
            id: scroll
            Layout.fillWidth:true; Layout.fillHeight:true
            contentWidth:availableWidth; clip:true
            Column {
                width:scroll.availableWidth; spacing:12
                Text { visible:p.jogo; width:parent.width; wrapMode:Text.Wrap; color:"#b6ccd6"; font.pixelSize:13
                    text:"Selecione os aplicativos que aceita fechar. Salve seu trabalho. Steam, Discord, jogos e serviços do Windows não entram nesta lista."
                }
                Repeater {
                    model:p.jogo ? [] : p.campos
                    Column {
                        id: campo
                        required property var modelData
                        width:parent.width; spacing:5
                        visible:modelData.aba===["Inteligência","Voz","Microfone","Sistema"][p.aba]
                        Text { text:campo.modelData.rotulo; color:"#adc6d4"; font.pixelSize:12 }
                        Loader {
                            width:parent.width
                            sourceComponent:campo.modelData.tipo==="bool" ? flag : (campo.modelData.tipo==="lista" || campo.modelData.chave==="microfone" ? lista : entrada)
                            Component {
                                id: flag
                                CheckBox {
                                    checked:!!campo.modelData.valor
                                    text:checked ? "Ativado" : "Desativado"
                                    palette.windowText:"#d4eaf4"
                                    onToggled:p.rascunho[campo.modelData.chave]=checked
                                }
                            }
                            Component {
                                id: lista
                                ComboBox {
                                    id: combo
                                    property bool mic:campo.modelData.chave==="microfone"
                                    property var dispositivos:(ponte.dados.preferencias||{}).microfones||[]
                                    model:mic ? dispositivos.map(function(d){return d.nome}) : campo.modelData.opcoes
                                    Component.onCompleted:{
                                        var v=campo.modelData.valor;
                                        currentIndex=mic ? dispositivos.findIndex(function(d){return d.valor===String(v)}) : model.indexOf(v);
                                    }
                                    onActivated:{
                                        p.rascunho[campo.modelData.chave]=mic ? dispositivos[currentIndex].valor : currentText;
                                    }
                                    palette.button:"#172d3c"; palette.buttonText:"#d4eaf4"; palette.text:"#d4eaf4"; palette.base:"#142636"; palette.highlight:"#296179"; palette.highlightedText:"white"
                                }
                            }
                            Component {
                                id: entrada
                                TextField {
                                    text:String(campo.modelData.valor)
                                    echoMode:campo.modelData.tipo==="senha" ? TextInput.Password : TextInput.Normal
                                    color:"#deeffa"; selectByMouse:true
                                    background:Rectangle { color:"#122333"; radius:6; border.color:parent.activeFocus ? "#55d8dd" : "#294353" }
                                    onTextEdited:p.rascunho[campo.modelData.chave]=text
                                }
                            }
                        }
                    }
                }
                Repeater {
                    model:p.jogo ? p.programas : []
                    CheckBox {
                        required property var modelData
                        text:modelData.rotulo; checked:!!p.selecionados[modelData.nome]
                        palette.windowText:"#d4eaf4"
                        onToggled:p.selecionados[modelData.nome]=checked
                    }
                }
                CheckBox {
                    visible:p.jogo
                    text:"Usar plano Alto desempenho, se disponível"; checked:p.alto
                    palette.windowText:"#d4eaf4"; onToggled:p.alto=checked
                }
                CheckBox {
                    visible:p.jogo
                    text:"Desativar Game Bar/gravação (evita quedas de FPS)"; checked:p.gamebar
                    palette.windowText:"#d4eaf4"; onToggled:p.gamebar=checked
                }
                CheckBox {
                    visible:p.jogo
                    text:"Pausar o Indexador de Pesquisa do Windows"; checked:p.indexacao
                    palette.windowText:"#d4eaf4"; onToggled:p.indexacao=checked
                }
                Text {
                    width:parent.width; wrapMode:Text.Wrap; color:"#7998ac"; font.pixelSize:12
                    text:p.jogo ? "Ao ativar: fecha as janelas dos aplicativos selecionados, pausa a indexação do Neymar e reduz a animação. O plano opcional pode aumentar consumo e aquecimento. Ao sair, tenta restaurar o plano anterior. Não reabre aplicativos nem garante aumento de FPS."
                         : "Campos de chave vazios mantêm as credenciais existentes. APIs online usam internet e podem ter cobrança. Para trocar a voz específica do Windows, consultar modelos ou remover chaves, use Opções avançadas."
                }
            }
        }
        Text {
            Layout.fillWidth:true; wrapMode:Text.Wrap; color:"#88e1d5"; font.pixelSize:12
            text:ponte.dados.aviso || (p.jogo ? ponte.dados.jogoStatus||"" : "Altere os campos e clique em Salvar.")
        }
        RowLayout {
            Layout.fillWidth:true
            Acao { text:"Salvar"; onClicked:p.salvar(false) }
            Acao { visible:p.jogo; text:"Salvar e ativar"; enabled:!ponte.dados.jogo; onClicked:confirmar.open() }
            Acao { visible:p.jogo; text:"Sair do modo de jogo"; onClicked:ponte.acao("desativar_jogo","") }
            Acao { visible:!p.jogo && p.aba===1; text:"Testar voz salva"; onClicked:ponte.acao("testar_voz","") }
            Item { Layout.fillWidth:true }
            Acao { text:"Opções avançadas"; onClicked:ponte.acao(p.jogo ? "jogo" : "config","") }
        }
    }
    Dialog {
        id: confirmar
        title:"Ativar modo de jogo?"
        anchors.centerIn:parent; width:Math.min(p.width-45,510); modal:true
        standardButtons:Dialog.Ok|Dialog.Cancel
        onAccepted:p.salvar(true)
        contentItem:Text {
            color:"#202a30"; wrapMode:Text.Wrap
            text:"O Neymar poderá fechar: "+p.programas.filter(function(x){return !!p.selecionados[x.nome]}).map(function(x){return x.rotulo}).join(", ")+
                ".\n\nSalve seu trabalho antes de confirmar."+ (p.alto ? "\nPlano Alto desempenho habilitado." : "\nO plano de energia não será alterado.")+
                (p.gamebar ? "\nGame Bar/gravação desativados durante o jogo (restaurados ao sair)." : "")+
                (p.indexacao ? "\nIndexador de Pesquisa do Windows pausado durante o jogo (retomado ao sair)." : "")
        }
    }
}
