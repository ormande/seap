from __future__ import annotations

"""
Base de dados simplificada de Natureza de Despesa (ND) e subelementos
relevantes para licitações.

Esta estrutura é usada no cruzamento ND × Itens (Estágio 3) para:
- mapear o elemento (30, 39, 52) para um nome amigável;
- fornecer contexto semântico ao modelo de IA;
- sugerir subelementos coerentes com a descrição do item.
"""

from typing import Dict, Any


ND_ELEMENTS: Dict[str, Dict[str, Any]] = {
    "30": {
        "nome": "Material de Consumo",
        "tipo": "material",
        "descricao": "Aquisição de bens físicos consumíveis",
        "palavras_chave": [
            "aquisição",
            "compra",
            "fornecimento",
            "material",
            "produto",
            "unidade",
            "peça",
            "kit",
        ],
        "subelementos": {
            "01": "Combustíveis e Lubrificantes Automotivos",
            "04": "Gás e Outros Materiais Engarrafados",
            "05": "Explosivos e Munições",
            "07": "Gêneros de Alimentação",
            "09": "Material Farmacológico",
            "10": "Material Odontológico",
            "11": "Material Químico",
            "14": "Material Educativo e Esportivo",
            "16": "Material de Expediente",
            "17": "Material de Processamento de Dados",
            "19": "Material de Acondicionamento e Embalagem",
            "20": "Material de Cama, Mesa e Banho",
            "21": "Material de Limpeza e Produtos de Higienização",
            "22": "Material de Copa e Cozinha",
            "23": "Material de Uniformes, Tecidos e Aviamentos",
            "24": "Material para Manutenção de Bens Imóveis",
            "25": "Material para Manutenção de Bens Móveis",
            "26": "Material Elétrico e Eletrônico",
            "28": "Material de Proteção e Segurança",
            "30": "Material para Comunicações",
            "35": "Material Laboratorial",
            "36": "Material Hospitalar",
            "39": "Material para Manutenção de Veículos",
            "42": "Ferramentas",
            "44": "Material de Sinalização Visual e Outros",
            "47": "Aquisição de Softwares de Base",
            "99": "Outros Materiais de Consumo",
        },
    },
    "39": {
        "nome": "Outros Serviços de Terceiros PJ",
        "tipo": "servico",
        "descricao": "Contratação de serviços de pessoa jurídica",
        "palavras_chave": [
            "manutenção",
            "serviço",
            "contratação",
            "instalação",
            "reparo",
            "conservação",
            "locação",
            "limpeza",
            "vigilância",
            "consultoria",
            "treinamento",
        ],
        "subelementos": {
            "05": "Serviços Técnicos Profissionais",
            "08": "Manutenção de Software",
            "10": "Locação de Imóveis",
            "11": "Locação de Softwares",
            "12": "Locação de Máquinas e Equipamentos",
            "16": "Manutenção e Conservação de Bens Imóveis",
            "17": "Manutenção e Conservação de Máquinas e Equipamentos",
            "19": "Manutenção e Conservação de Veículos",
            "20": "Manutenção e Conservação de Bens Móveis",
            "33": "Fornecimento de Alimentação",
            "40": "Serviços de Seleção e Treinamento",
            "42": "Serviços de Telecomunicações",
            "43": "Serviços de Energia Elétrica",
            "44": "Serviços de Água e Esgoto",
            "47": "Serviços de Comunicação em Geral",
            "49": "Serviços de Processamento de Dados",
            "62": "Serviços de Apoio Administrativo",
            "70": "Confecção de Uniformes, Bandeiras e Flâmulas",
            "74": "Serviços de Cópias e Reprodução de Documentos",
            "77": "Vigilância Ostensiva/Monitorada",
            "78": "Limpeza e Conservação",
            "99": "Outros Serviços de Terceiros PJ",
        },
    },
    "52": {
        "nome": "Equipamentos e Material Permanente",
        "tipo": "equipamento",
        "descricao": "Aquisição de bens duráveis/permanentes",
        "palavras_chave": [
            "equipamento",
            "aparelho",
            "máquina",
            "veículo",
            "mobiliário",
            "permanente",
        ],
        "subelementos": {
            "02": "Aparelhos de Medição e Orientação",
            "03": "Aparelhos e Equipamentos de Comunicação",
            "06": "Aparelhos e Utensílios Domésticos",
            "08": "Aparelhos e Equipamentos Médicos/Odontológicos",
            "12": "Equipamentos de Proteção, Segurança e Socorro",
            "14": "Máquinas e Equipamentos de Natureza Industrial",
            "17": "Equipamentos para Áudio, Vídeo e Foto",
            "18": "Máquinas, Utensílios e Equipamentos Diversos",
            "19": "Equipamentos de Processamento de Dados",
            "20": "Máquinas, Instalações e Utensílios de Escritório",
            "21": "Máquinas, Ferramentas e Utensílios de Oficina",
            "22": "Equipamentos e Utensílios Hidráulicos e Elétricos",
            "99": "Outros Equipamentos e Material Permanente",
        },
    },
}

