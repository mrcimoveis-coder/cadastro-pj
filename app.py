import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
import io
import re
import unicodedata
import urllib.request
import streamlit as st

# ReportLab para geração do PDF
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

# -----------------------------------------------------------------------------
# FUNÇÕES AUXILIARES DE VALIDAÇÃO E FORMATAÇÃO
# -----------------------------------------------------------------------------
def validar_cnpj(cnpj_raw: str) -> bool:
    cnpj = re.sub(r'\D', '', str(cnpj_raw))
    if len(cnpj) != 14 or cnpj == cnpj[0] * 14:
        return False
    pesos_1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    pesos_2 = [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    soma_1 = sum(int(cnpj[i]) * pesos_1[i] for i in range(12))
    resto_1 = soma_1 % 11
    digito_1 = 0 if resto_1 < 2 else 11 - resto_1
    if int(cnpj[12]) != digito_1:
        return False
    soma_2 = sum(int(cnpj[i]) * pesos_2[i] for i in range(13))
    resto_2 = soma_2 % 11
    digito_2 = 0 if resto_2 < 2 else 11 - resto_2
    return int(cnpj[13]) == digito_2

def validar_cpf(cpf_raw: str) -> bool:
    cpf = re.sub(r'\D', '', str(cpf_raw))
    if len(cpf) != 11 or cpf == cpf[0] * 11:
        return False
    for i in range(9, 11):
        val = sum(int(cpf[num]) * ((i + 1) - num) for num in range(0, i))
        digit = ((val * 10) % 11) % 10
        if str(digit) != cpf[i]:
            return False
    return True

def formatar_cnpj(val: str) -> str:
    d = re.sub(r'\D', '', str(val))
    if len(d) == 14:
        return f"{d[:2]}.{d[2:5]}.{d[5:8]}/{d[8:12]}-{d[12:]}"
    return val

def formatar_cpf(val: str) -> str:
    d = re.sub(r'\D', '', str(val))
    if len(d) == 11:
        return f"{d[:3]}.{d[3:6]}.{d[6:9]}-{d[9:]}"
    return val

def formatar_telefone(val: str) -> str:
    d = re.sub(r'\D', '', str(val))
    if len(d) == 11:
        return f"({d[:2]}) {d[2:7]}-{d[7:]}"
    elif len(d) == 10:
        return f"({d[:2]}) {d[2:6]}-{d[6:]}"
    return val

def formatar_data(val: str) -> str:
    d = re.sub(r'\D', '', str(val))
    if len(d) == 8:
        return f"{d[:2]}/{d[2:4]}/{d[4:]}"
    return val

def formatar_moeda(val: str) -> str:
    if not val:
        return ""
    clean = str(val).upper().replace("R$", "").strip()
    if not clean:
        return ""
    clean_digits = re.sub(r'[^\d,.]', '', clean)
    if ',' in clean_digits:
        clean_digits = clean_digits.replace('.', '').replace(',', '.')
    else:
        if clean_digits.count('.') > 1:
            clean_digits = clean_digits.replace('.', '')
        elif clean_digits.count('.') == 1:
            parts = clean_digits.split('.')
            if len(parts[1]) != 2:
                clean_digits = clean_digits.replace('.', '')
    try:
        num = float(clean_digits)
        formatted = f"{num:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        return f"R$ {formatted}"
    except ValueError:
        return val

def sanitizar_nome_arquivo(nome):
    """Higieniza nomes de arquivos para impedir rejeição do Gmail (evita 'noname')"""
    n = unicodedata.normalize('NFKD', str(nome)).encode('ASCII', 'ignore').decode('utf-8')
    n = re.sub(r'[^a-zA-Z0-9.]', '_', n)
    n = re.sub(r'\.+', '.', n)
    return re.sub(r'_+', '_', n).strip('_')

# -----------------------------------------------------------------------------
# GERADOR DE PDF DA FICHA CADASTRAL PJ
# -----------------------------------------------------------------------------
def gerar_pdf_ficha_pj(dados: dict) -> bytes:
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=36, leftMargin=36, topMargin=36, bottomMargin=36)
    styles = getSampleStyleSheet()
    
    style_title = ParagraphStyle('Title', parent=styles['Heading1'], fontSize=13, textColor=colors.HexColor("#C4001A"), spaceAfter=8)
    style_section = ParagraphStyle('Section', parent=styles['Heading2'], fontSize=11, textColor=colors.HexColor("#2B2B2B"), spaceBefore=10, spaceAfter=5)
    style_body = ParagraphStyle('Body', parent=styles['Normal'], fontSize=9, leading=12, textColor=colors.HexColor("#333333"))
    style_bold = ParagraphStyle('Bold', parent=style_body, fontName='Helvetica-Bold')

    elements = []

    try:
        logo_url = "https://raw.githubusercontent.com/mrcimoveis-coder/intranet/main/logo.jpeg"
        logo_data = urllib.request.urlopen(logo_url).read()
        logo_io = io.BytesIO(logo_data)
        img = Image(logo_io, width=140, height=48)
        img.hAlign = 'LEFT'
        elements.append(img)
        elements.append(Spacer(1, 8))
    except Exception:
        pass

    elements.append(Paragraph("<b>FICHA CADASTRAL DE LOCAÇÃO — PESSOA JURÍDICA (PJ)</b>", style_title))
    elements.append(HRFlowable(width="100%", thickness=2, color=colors.HexColor("#C4001A"), spaceAfter=12))

    def montar_tabela(dados_sec):
        data_table = []
        for k, v in dados_sec.items():
            if v:
                p_key = Paragraph(f"<b>{k}:</b>", style_bold)
                p_val = Paragraph(str(v), style_body)
                data_table.append([p_key, p_val])
        if not data_table:
            return Spacer(1, 1)
        t = Table(data_table, colWidths=[160, 360])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#F8FAFC")),
            ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#E2E8F0")),
            ('VALIGN', (0,0), (-1,-1), 'TOP'),
            ('PADDING', (0,0), (-1,-1), 4),
        ]))
        return t

    # 1. Identificação da Empresa e Imóvel
    sec1 = {
        "Razão Social": dados["razao_social"],
        "Nome Fantasia": dados["nome_fantasia"],
        "CNPJ": dados["cnpj"],
        "Inscrição Estadual": dados["insc_estadual"],
        "Inscrição Municipal": dados["insc_municipal"],
        "Data de Fundação": dados["dt_fundacao"],
        "Ramo de Atividade": dados["ramo_atividade"],
        "E-mail Corporativo": dados["email_empresa"],
        "Telefone Comercial": dados["tel_empresa"],
        "Endereço da Sede": dados["endereco_sede"],
        "Faturamento Médio Mensal": dados["faturamento"],
        "Imóvel Pretendido": dados["endereco_imovel"],
        "Valor do Aluguel Pretendido": dados["valor_aluguel"],
        "Garantia Oferecida": f"{dados['garantia']} ({dados['detalhe_garantia']})" if dados.get('detalhe_garantia') else dados['garantia'],
        "Finalidade da Locação": dados["finalidade_locacao"]
    }
    elements.append(Paragraph("1. Dados da Empresa e Imóvel Pretendido", style_section))
    elements.append(montar_tabela(sec1))
    elements.append(Spacer(1, 8))

    # 2. Quadro de Sócios / Representantes Legais
    elements.append(Paragraph(f"2. Quadro de Sócios e Representantes Legais ({len(dados['socios'])} informado(s))", style_section))
    for idx, s in enumerate(dados["socios"], start=1):
        sec_socio = {
            "Nome Completo": s["nome"],
            "CPF": s["cpf"],
            "RG": f"{s['rg']} (Órgão: {s['rg_orgao']})",
            "Data de Nascimento": s["dt_nasc"],
            "Estado Civil": s["estado_civil"],
            "Tipo de Participação": s["tipo"],
            "Participação na Sociedade": f"{s['pct']}%",
            "Celular": s["celular"],
            "E-mail Pessoal": s["email"],
            "Endereço Residencial": s["endereco"]
        }
        elements.append(Paragraph(f"<b>Sócio/Representante {idx}</b>", style_body))
        elements.append(montar_tabela(sec_socio))
        elements.append(Spacer(1, 6))

    # 3. Referências e Observações
    sec3 = {
        "Referências Bancárias": dados["ref_bancarias"],
        "Referências Comerciais": dados["ref_comerciais"],
        "Observações": dados["observacoes"]
    }
    elements.append(Paragraph("3. Referências e Observações", style_section))
    elements.append(montar_tabela(sec3))

    doc.build(elements)
    buffer.seek(0)
    return buffer.getvalue()


# -----------------------------------------------------------------------------
# INTERFACE STREAMLIT
# -----------------------------------------------------------------------------
st.set_page_config(page_title="Ficha Cadastral PJ | MRC Imóveis", page_icon="🏢", layout="centered")

# ESTADO DE ENVIO COM SUCESSO (TELA DE AGRADECIMENTO)
if "enviado_sucesso" not in st.session_state:
    st.session_state.enviado_sucesso = False

if st.session_state.enviado_sucesso:
    st.balloons()
    try:
        st.image("https://raw.githubusercontent.com/mrcimoveis-coder/intranet/main/logo.jpeg", width=260)
    except Exception:
        pass
    
    st.success("✅ **Ficha Cadastral PJ e Documentos Enviados com Sucesso!**")
    st.markdown("""
    ### Obrigado por enviar os dados da sua empresa para a **MRC Imóveis**! 🎉
    
    A ficha cadastral corporativa e a documentação dos sócios foram encaminhadas para o nosso setor de análise de locação.
    
    **O que acontece agora?**
    * Nossa equipe iniciará a análise cadastral e financeira da empresa.
    * Entraremos em contato em breve através do e-mail corporativo ou telefone informado.
    
    ---
    📬 **Contatos Úteis:**
    * **E-mail:** aluguel@mrcimoveis.com.br / comercial@mrcimoveis.com.br
    """)
    st.markdown("---")
    if st.button("🔄 Preencher outro cadastro PJ"):
        st.session_state.enviado_sucesso = False
        st.rerun()
    st.stop()

# FORMULÁRIO PADRÃO
try:
    st.image("https://raw.githubusercontent.com/mrcimoveis-coder/intranet/main/logo.jpeg", width=260)
except Exception:
    pass

st.title("🏢 Ficha Cadastral - Pessoa Jurídica")
st.write("Preencha os dados da empresa, representantes legais e anexe a documentação necessária.")

# 1. Dados da Empresa e Imóvel Pretendido
st.subheader("1. Dados da Empresa e Imóvel Pretendido")
col_e1, col_e2 = st.columns(2)
with col_e1:
    razao_social = st.text_input("Razão Social *")
    nome_fantasia = st.text_input("Nome Fantasia")
    cnpj_raw = st.text_input("CNPJ *", placeholder="00.000.000/0001-00")
    dt_fundacao_raw = st.text_input("Data de Fundação / Abertura *", placeholder="DD/MM/AAAA")
    insc_estadual = st.text_input("Inscrição Estadual (ou Isento)")
with col_e2:
    insc_municipal = st.text_input("Inscrição Municipal")
    ramo_atividade = st.text_input("Ramo de Atividade / Objeto Social *")
    tel_empresa_raw = st.text_input("Telefone Comercial Empresa *", placeholder="(61) 3000-0000")
    email_empresa = st.text_input("E-mail Corporativo *", placeholder="contato@empresa.com.br")
    faturamento_raw = st.text_input("Faturamento Médio Mensal (R$) *", placeholder="Ex: 50000")

endereco_sede = st.text_input("Endereço Completo da Sede / Matriz (com CEP) *")
endereco_imovel = st.text_input("Endereço do Imóvel a ser Alugado *")
valor_aluguel_raw = st.text_input("Valor do Aluguel Pretendido (R$) (opcional)", placeholder="Ex: 5000")
finalidade_locacao = st.text_input("Finalidade da Locação / Uso do Imóvel *", placeholder="Ex: Escritório administrativo, loja de roupas...")

# 2. Garantia da Locação
st.subheader("2. Garantia da Locação")
garantia = st.selectbox(
    "Garantia oferecida *",
    [
        "2 Fiadores (PF) do DF com renda e imóvel",
        "Fiador Pessoa Jurídica (PJ)",
        "Caução / Título de Capitalização",
        "Seguro Fiança",
        "Fiança Bancária / Associação",
        "CredPago",
        "Outra"
    ]
)
detalhe_garantia = st.text_input("Detalhamento da garantia (caso necessário)")

# 3. Quadro de Sócios e Representantes Legais
st.markdown("---")
st.subheader("3. Quadro de Sócios e Representantes Legais")
st.caption("Informe a quantidade total de sócios/representantes e preencha os dados individuais de cada um.")

num_socios = st.number_input("Quantos sócios / representantes a empresa possui? *", min_value=1, max_value=10, value=1, step=1)

socios_inputs = []
for i in range(int(num_socios)):
    st.markdown(f"### Sócio / Representante Legal {i+1}")
    col_s1, col_s2 = st.columns(2)
    with col_s1:
        s_nome = st.text_input("Nome Completo *", key=f"s_nome_{i}")
        s_cpf_raw = st.text_input("CPF *", placeholder="000.000.000-00", key=f"s_cpf_{i}")
        s_rg = st.text_input("Número do RG *", key=f"s_rg_{i}")
        s_rg_orgao = st.text_input("Órgão Emissor / UF *", placeholder="Ex: SSP/DF", key=f"s_rg_org_{i}")
        s_dt_nasc_raw = st.text_input("Data de Nascimento *", placeholder="DD/MM/AAAA", key=f"s_dtnasc_{i}")
    with col_s2:
        s_tipo = st.selectbox("Função na Sociedade *", ["Sócio-Administrador", "Sócio (Sem adm)", "Procurador / Rep. Legal"], key=f"s_tipo_{i}")
        s_pct = st.text_input("Percentual de Participação (%) *", placeholder="Ex: 50", key=f"s_pct_{i}")
        s_estado_civil = st.selectbox("Estado Civil *", ["Solteiro(a)", "Casado(a)", "União Estável", "Divorciado(a)", "Viúvo(a)"], key=f"s_estcivil_{i}")
        s_celular_raw = st.text_input("Telefone Celular *", placeholder="(61) 90000-0000", key=f"s_cel_{i}")
        s_email = st.text_input("E-mail Pessoal *", key=f"s_email_{i}")
    
    s_endereco = st.text_input("Endereço Residencial Completo (com CEP) *", key=f"s_end_{i}")

    socios_inputs.append({
        "nome": s_nome, "cpf_raw": s_cpf_raw, "rg": s_rg, "rg_orgao": s_rg_orgao,
        "dt_nasc_raw": s_dt_nasc_raw, "tipo": s_tipo, "pct": s_pct,
        "estado_civil": s_estado_civil, "celular_raw": s_celular_raw,
        "email": s_email, "endereco": s_endereco
    })

# 4. Referências
st.markdown("---")
st.subheader("4. Referências")
ref_bancarias = st.text_input("Referências Bancárias (Banco, Agência, Conta e Gerente) *")
ref_comerciais = st.text_area("Referências Comerciais (Nome e Telefone de 02 Fornecedores/Clientes) *")

# 5. Documentos
st.markdown("---")
st.subheader("5. Envio de Documentos (Anexos)")

st.warning("⚠️ **Atenção para enviar vários arquivos:** Para colocar mais de um arquivo no mesmo campo, você deve **selecionar todos eles de uma só vez** na janela que abrir. Se você anexar um e depois clicar no botão para anexar o segundo, o primeiro será substituído.")

st.info("Formatos aceitos: PDF, JPG, PNG.")

doc_contrato_social = st.file_uploader("1. Contrato Social / Estatuto Social (última alteração consolidada) *", accept_multiple_files=True)
doc_cnpj = st.file_uploader("2. Cartão CNPJ Atualizado *", accept_multiple_files=True)
doc_balanco = st.file_uploader("3. Balanço Patrimonial do Último Período Entregue *", accept_multiple_files=True)
doc_faturamento = st.file_uploader("4. Comprovante de Faturamento (DRE / Balancete / PGDAS IRPJ) *", accept_multiple_files=True)
doc_id_socios = st.file_uploader("5. Documentos de Identificação dos Sócios (RG/CPF ou CNH) *", accept_multiple_files=True)
doc_comprovante_empresa = st.file_uploader("6. Comprovante de Endereço da Empresa *", accept_multiple_files=True)

observacoes = st.text_area("Observações Adicionais")
aceito = st.checkbox("Declaro que as informações prestadas são verdadeiras e autorizo a análise cadastral pela MRC Imóveis. *")

btn_enviar = st.button("🚀 Enviar Cadastro PJ e Documentos", type="primary", use_container_width=True)

# -----------------------------------------------------------------------------
# PROCESSAMENTO DO ENVIO
# -----------------------------------------------------------------------------
if btn_enviar:
    cnpj = formatar_cnpj(cnpj_raw)
    dt_fundacao = formatar_data(dt_fundacao_raw)
    tel_empresa = formatar_telefone(tel_empresa_raw)
    faturamento = formatar_moeda(faturamento_raw)
    valor_aluguel = formatar_moeda(valor_aluguel_raw)

    socios_processados = []
    erros_socios = False
    for s in socios_inputs:
        cpf_fmt = formatar_cpf(s["cpf_raw"])
        dt_nasc_fmt = formatar_data(s["dt_nasc_raw"])
        celular_fmt = formatar_telefone(s["celular_raw"])

        if not s["nome"] or not s["cpf_raw"] or not s["rg"] or not s["rg_orgao"] or not s["pct"] or not s["celular_raw"] or not s["endereco"]:
            erros_socios = True
        elif not validar_cpf(s["cpf_raw"]):
            st.error(f"❌ O CPF do sócio {s['nome']} é inválido.")
            erros_socios = True

        socios_processados.append({
            "nome": s["nome"], "cpf": cpf_fmt, "rg": s["rg"], "rg_orgao": s["rg_orgao"],
            "dt_nasc": dt_nasc_fmt, "tipo": s["tipo"], "pct": s["pct"],
            "estado_civil": s["estado_civil"], "celular": celular_fmt,
            "email": s["email"], "endereco": s["endereco"]
        })

    erros = []
    if not aceito:
        erros.append("Você precisa marcar a caixa de declaração autorizando a análise.")
    if not razao_social or not cnpj_raw or not ramo_atividade or not tel_empresa_raw or not email_empresa or not endereco_sede or not endereco_imovel or not finalidade_locacao or not faturamento_raw:
        erros.append("Preencha todos os campos obrigatórios (*) da empresa e imóvel pretendido.")
    if not validar_cnpj(cnpj_raw):
        erros.append("O CNPJ digitado é inválido. Por favor, verifique o número informado.")
    if erros_socios:
        erros.append("Preencha todos os campos obrigatórios de todos os sócios/representantes.")
    if not ref_bancarias or not ref_comerciais:
        erros.append("Preencha as referências bancárias e comerciais.")

    if erros:
        for err in erros:
            st.error(f"⚠️ {err}")
    else:
        with st.spinner("Gerando Ficha Cadastral PJ em PDF e enviando e-mail... Aguarde..."):
            try:
                dados_form = {
                    "razao_social": razao_social, "nome_fantasia": nome_fantasia, "cnpj": cnpj,
                    "dt_fundacao": dt_fundacao, "insc_estadual": insc_estadual, "insc_municipal": insc_municipal,
                    "ramo_atividade": ramo_atividade, "tel_empresa": tel_empresa, "email_empresa": email_empresa,
                    "faturamento": faturamento, "endereco_sede": endereco_sede, "endereco_imovel": endereco_imovel,
                    "valor_aluguel": valor_aluguel, "finalidade_locacao": finalidade_locacao, "garantia": garantia,
                    "detalhe_garantia": detalhe_garantia, "socios": socios_processados,
                    "ref_bancarias": ref_bancarias, "ref_comerciais": ref_comerciais, "observacoes": observacoes
                }

                pdf_bytes = gerar_pdf_ficha_pj(dados_form)

                smtp_server = st.secrets["smtp"]["server"]
                smtp_port = st.secrets["smtp"]["port"]
                sender_email = st.secrets["smtp"]["email"]
                sender_password = st.secrets["smtp"]["password"]
                receiver_emails = ["aluguel@mrcimoveis.com.br", "comercial@mrcimoveis.com.br"]

                msg = MIMEMultipart()
                msg['From'] = sender_email
                msg['To'] = ", ".join(receiver_emails)
                msg['Subject'] = f"NOVO CADASTRO PJ - {razao_social}"

                html_body = f"""
                <html>
                <body style="font-family: Arial, sans-serif; color: #333333; background-color: #F4F6F8; padding: 20px;">
                    <div style="max-width: 650px; margin: 0 auto; background-color: #ffffff; border-radius: 8px; border-top: 5px solid #C4001A; padding: 25px; box-shadow: 0 4px 10px rgba(0,0,0,0.05);">
                        <h2 style="color: #C4001A; margin-top: 0;">Novo Cadastro PJ Recebido — MRC Imóveis</h2>
                        <p><strong>Empresa:</strong> {razao_social} (CNPJ: {cnpj})</p>
                        <p><strong>E-mail:</strong> {email_empresa} | <strong>Telefone:</strong> {tel_empresa}</p>
                        <p><strong>Imóvel Pretendido:</strong> {endereco_imovel}</p>
                        <p><strong>Faturamento Mensal:</strong> {faturamento}</p>
                        <hr style="border: 0; border-top: 1px solid #E2E8F0; margin: 20px 0;">
                        <p style="color: #6C757D; font-size: 0.9em;">📌 <strong>A Ficha Cadastral PJ completa está anexada em PDF (Ficha_Cadastral_PJ.pdf), juntamente com o Balanço Patrimonial e demais documentos.</strong></p>
                    </div>
                </body>
                </html>
                """
                msg.attach(MIMEText(html_body, 'html'))

                part_pdf = MIMEBase('application', 'pdf')
                part_pdf.set_payload(pdf_bytes)
                encoders.encode_base64(part_pdf)
                nome_pdf_seguro = sanitizar_nome_arquivo(f"Ficha_Cadastral_PJ_{razao_social}.pdf")
                part_pdf.add_header('Content-Disposition', 'attachment', filename=nome_pdf_seguro)
                msg.attach(part_pdf)

                def anexar_uploads(lista_uploads, categoria):
                    if lista_uploads:
                        for upload in lista_uploads:
                            upload.seek(0)
                            file_bytes = upload.read()
                            if not file_bytes:
                                continue
                            
                            nome_seguro = sanitizar_nome_arquivo(upload.name)
                            nome_final = f"{categoria}_{nome_seguro}"
                            
                            part = MIMEBase('application', 'octet-stream', name=nome_final)
                            part.set_payload(file_bytes)
                            encoders.encode_base64(part)
                            part.add_header('Content-Disposition', 'attachment', filename=nome_final)
                            msg.attach(part)

                anexar_uploads(doc_contrato_social, "CONTRATO_SOCIAL")
                anexar_uploads(doc_cnpj, "CARTAO_CNPJ")
                anexar_uploads(doc_balanco, "BALANCO_PATRIMONIAL")
                anexar_uploads(doc_faturamento, "FATURAMENTO")
                anexar_uploads(doc_id_socios, "ID_SOCIOS")
                anexar_uploads(doc_comprovante_empresa, "ENDERECO_EMPRESA")

                server = smtplib.SMTP(smtp_server, smtp_port)
                server.starttls()
                server.login(sender_email, sender_password)
                server.sendmail(sender_email, receiver_emails, msg.as_string())
                server.quit()

                # REDIRECIONA PARA A TELA DE AGRADECIMENTO
                st.session_state.enviado_sucesso = True
                st.rerun()

            except Exception as e:
                st.error(f"❌ Erro ao processar o envio: {e}")
