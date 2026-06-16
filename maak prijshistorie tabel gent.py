import pandas as pd

export = pd.read_excel('SearchInvoiceLines_2026-06-12_08_20_07.xlsx')

export['AffiliateId'] = 'Gent'


export['Factuurdatum'] = export['Datum'].dt.strftime('%d-%m-%Y')
export = export[~export['Kortingspercentage'].astype(str).str.contains('<', na=False)]

export['Kortingspercentage'] = (
    export['Kortingspercentage']
    .astype(str)
    .str.replace(',', '.', regex=False)
    .astype(float)
)

export['Eenheidsprijs'] = pd.to_numeric(export['Eenheidsprijs'], errors='coerce')
export['Verkoopprijs'] = (export['Eenheidsprijs'] * (1-export['Kortingspercentage'])).round(2)
        
export = export.rename(columns={
        'Artikelcode': 'Onderdeelnummer',
        'Contact': 'Relatie',
        'AffiliateId': 'Vestiging',
        'Kortingspercentage': 'Toegepaste kortingspercentage',
    })

export = export[['Onderdeelnummer', 'Verkoopprijs', 'Toegepaste kortingspercentage', 'Relatie', 'Vestiging', 'Factuurdatum']]

export.to_excel('onderdelen gent.xlsx', index=False)
