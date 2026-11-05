"""Synthetic schema-complete NF-e fixture; not an accounting/tax golden approval."""
from test_mg_homologation_authorization import _request


def unsigned_golden_request():
    from dataclasses import replace
    source = _request()
    key = source.access_key.value
    xml = f"""<enviNFe xmlns="http://www.portalfiscal.inf.br/nfe" versao="4.00">
<idLote>1</idLote><indSinc>1</indSinc><NFe><infNFe Id="NFe{key}" versao="4.00">
<ide><cUF>31</cUF><cNF>12345678</cNF><natOp>VENDA TESTE</natOp><mod>55</mod>
<serie>1</serie><nNF>1</nNF><dhEmi>2026-11-05T12:00:00-03:00</dhEmi><tpNF>1</tpNF>
<idDest>1</idDest><cMunFG>3106200</cMunFG><tpImp>1</tpImp><tpEmis>1</tpEmis>
<cDV>{key[-1]}</cDV><tpAmb>2</tpAmb><finNFe>1</finNFe><indFinal>1</indFinal>
<indPres>1</indPres><procEmi>0</procEmi><verProc>NFCore-SYNTHETIC</verProc></ide>
<emit><CNPJ>11222333000181</CNPJ><xNome>EMITENTE SINTETICO PARA TESTES</xNome>
<enderEmit><xLgr>RUA DE TESTE</xLgr><nro>1</nro><xBairro>TESTE</xBairro>
<cMun>3106200</cMun><xMun>BELO HORIZONTE</xMun><UF>MG</UF><CEP>30110000</CEP>
<cPais>1058</cPais><xPais>BRASIL</xPais></enderEmit><IE>062307904008</IE><CRT>3</CRT></emit>
<dest><CNPJ>12345678000195</CNPJ>
<xNome>NF-E EMITIDA EM AMBIENTE DE HOMOLOGACAO - SEM VALOR FISCAL</xNome>
<enderDest><xLgr>RUA SINTETICA</xLgr><nro>2</nro><xBairro>TESTE</xBairro>
<cMun>3106200</cMun><xMun>BELO HORIZONTE</xMun><UF>MG</UF><CEP>30110000</CEP>
<cPais>1058</cPais><xPais>BRASIL</xPais></enderDest><indIEDest>9</indIEDest></dest>
<det nItem="1"><prod><cProd>TESTE-001</cProd><cEAN>SEM GTIN</cEAN>
<xProd>PRODUTO SINTETICO PARA TESTE</xProd><NCM>39269090</NCM><CFOP>5102</CFOP>
<uCom>UN</uCom><qCom>1.0000</qCom><vUnCom>1.0000000000</vUnCom><vProd>1.00</vProd>
<cEANTrib>SEM GTIN</cEANTrib><uTrib>UN</uTrib><qTrib>1.0000</qTrib>
<vUnTrib>1.0000000000</vUnTrib><indTot>1</indTot></prod>
<imposto><ICMS><ICMS00><orig>0</orig><CST>00</CST><modBC>3</modBC>
<vBC>1.00</vBC><pICMS>18.0000</pICMS><vICMS>0.18</vICMS></ICMS00></ICMS>
<PIS><PISNT><CST>07</CST></PISNT></PIS>
<COFINS><COFINSNT><CST>07</CST></COFINSNT></COFINS></imposto></det>
<total><ICMSTot><vBC>1.00</vBC><vICMS>0.18</vICMS><vICMSDeson>0.00</vICMSDeson>
<vFCP>0.00</vFCP><vBCST>0.00</vBCST><vST>0.00</vST><vFCPST>0.00</vFCPST>
<vFCPSTRet>0.00</vFCPSTRet><vProd>1.00</vProd><vFrete>0.00</vFrete><vSeg>0.00</vSeg>
<vDesc>0.00</vDesc><vII>0.00</vII><vIPI>0.00</vIPI><vIPIDevol>0.00</vIPIDevol>
<vPIS>0.00</vPIS><vCOFINS>0.00</vCOFINS><vOutro>0.00</vOutro><vNF>1.00</vNF>
</ICMSTot></total><transp><modFrete>9</modFrete></transp>
<pag><detPag><indPag>0</indPag><tPag>01</tPag><vPag>1.00</vPag></detPag></pag>
</infNFe></NFe></enviNFe>"""
    return replace(source, signed_xml=xml.encode())


def verify_soap_signature(payload, material):
    import base64
    import hashlib

    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import padding
    from cryptography.hazmat.primitives.serialization import pkcs12
    from lxml import etree

    root = etree.fromstring(payload)
    ds = "http://www.w3.org/2000/09/xmldsig#"
    signature = root.find(f".//{{{ds}}}Signature")
    info = signature.find(f"{{{ds}}}SignedInfo")
    reference = info.find(f"{{{ds}}}Reference")
    target_id = reference.get("URI")[1:]
    targets = root.xpath("//*[@Id=$identity]", identity=target_id)
    assert len(targets) == 1
    actual_digest = base64.b64encode(
        hashlib.sha1(etree.tostring(targets[0], method="c14n")).digest()
    ).decode()
    assert reference.findtext(f"{{{ds}}}DigestValue") == actual_digest
    _, cert, _ = pkcs12.load_key_and_certificates(material.pkcs12_bytes, material.password)
    cert.public_key().verify(
        base64.b64decode(signature.findtext(f"{{{ds}}}SignatureValue")),
        etree.tostring(info, method="c14n"), padding.PKCS1v15(), hashes.SHA1(),
    )
