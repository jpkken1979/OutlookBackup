---
name: pdf-generation-patterns
description: Skill description for pdf-generation-patterns
type: feature
---

# PDF Generation Patterns

> Patrones para generación de PDFs: reportes, facturas, documentos.

---

## Descripción

Esta skill cubre generación de PDFs usando diferentes enfoques: HTML-to-PDF, librerías programáticas, y templates.

---

## Comparativa de Librerías

| Librería | Lenguaje | Enfoque | Pros | Contras |
|----------|----------|---------|------|---------|
| **Puppeteer** | Node.js | HTML→PDF | Fidelidad alta, CSS completo | Pesado (Chromium) |
| **PDFKit** | Node.js | Programático | Ligero, control total | Más código |
| **jsPDF** | Browser/Node | Programático | Cliente-side | Limitado en estilos |
| **React-PDF** | React | Componentes | Declarativo, reusable | Solo React |
| **WeasyPrint** | Python | HTML→PDF | CSS Paged Media | Setup más complejo |
| **ReportLab** | Python | Programático | Muy potente | Curva de aprendizaje |

---

## Puppeteer (HTML to PDF)

### Setup

```typescript
import puppeteer from 'puppeteer';

const browser = await puppeteer.launch({
  headless: 'new',
  args: ['--no-sandbox', '--disable-setuid-sandbox'],
});
```

### Generar PDF desde HTML

```typescript
interface PDFOptions {
  html: string;
  headerTemplate?: string;
  footerTemplate?: string;
  margin?: { top: string; bottom: string; left: string; right: string };
}

async function generatePDF(options: PDFOptions): Promise<Buffer> {
  const page = await browser.newPage();

  await page.setContent(options.html, {
    waitUntil: 'networkidle0',
  });

  const pdf = await page.pdf({
    format: 'A4',
    printBackground: true,
    margin: options.margin || {
      top: '20mm',
      bottom: '20mm',
      left: '15mm',
      right: '15mm',
    },
    displayHeaderFooter: !!(options.headerTemplate || options.footerTemplate),
    headerTemplate: options.headerTemplate || '',
    footerTemplate: options.footerTemplate || `
      <div style="font-size: 10px; text-align: center; width: 100%;">
        <span class="pageNumber"></span> / <span class="totalPages"></span>
      </div>
    `,
  });

  await page.close();

  return pdf;
}
```

### Template de Factura

```typescript
function generateInvoiceHTML(invoice: Invoice): string {
  return `
    <!DOCTYPE html>
    <html>
    <head>
      <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: 'Helvetica', sans-serif; font-size: 12px; color: #333; }
        .invoice { padding: 40px; }
        .header { display: flex; justify-content: space-between; margin-bottom: 40px; }
        .logo { font-size: 24px; font-weight: bold; color: #2563eb; }
        .invoice-info { text-align: right; }
        .invoice-number { font-size: 18px; font-weight: bold; }
        .parties { display: flex; justify-content: space-between; margin-bottom: 40px; }
        .party { width: 45%; }
        .party-title { font-weight: bold; color: #666; margin-bottom: 10px; }
        table { width: 100%; border-collapse: collapse; margin-bottom: 30px; }
        th { background: #f3f4f6; padding: 12px; text-align: left; border-bottom: 2px solid #e5e7eb; }
        td { padding: 12px; border-bottom: 1px solid #e5e7eb; }
        .amount { text-align: right; }
        .totals { margin-left: auto; width: 300px; }
        .totals tr td { padding: 8px 12px; }
        .total-row { font-weight: bold; font-size: 14px; background: #f3f4f6; }
        .footer { margin-top: 40px; padding-top: 20px; border-top: 1px solid #e5e7eb; }
        .payment-info { margin-top: 20px; }
      </style>
    </head>
    <body>
      <div class="invoice">
        <div class="header">
          <div class="logo">${invoice.company.name}</div>
          <div class="invoice-info">
            <div class="invoice-number">Invoice #${invoice.number}</div>
            <div>Date: ${formatDate(invoice.date)}</div>
            <div>Due: ${formatDate(invoice.dueDate)}</div>
          </div>
        </div>

        <div class="parties">
          <div class="party">
            <div class="party-title">From:</div>
            <div>${invoice.company.name}</div>
            <div>${invoice.company.address}</div>
            <div>${invoice.company.email}</div>
          </div>
          <div class="party">
            <div class="party-title">Bill To:</div>
            <div>${invoice.customer.name}</div>
            <div>${invoice.customer.address}</div>
            <div>${invoice.customer.email}</div>
          </div>
        </div>

        <table>
          <thead>
            <tr>
              <th>Description</th>
              <th>Qty</th>
              <th class="amount">Unit Price</th>
              <th class="amount">Amount</th>
            </tr>
          </thead>
          <tbody>
            ${invoice.items.map(item => `
              <tr>
                <td>${item.description}</td>
                <td>${item.quantity}</td>
                <td class="amount">${formatCurrency(item.unitPrice)}</td>
                <td class="amount">${formatCurrency(item.quantity * item.unitPrice)}</td>
              </tr>
            `).join('')}
          </tbody>
        </table>

        <table class="totals">
          <tr>
            <td>Subtotal:</td>
            <td class="amount">${formatCurrency(invoice.subtotal)}</td>
          </tr>
          <tr>
            <td>Tax (${invoice.taxRate}%):</td>
            <td class="amount">${formatCurrency(invoice.tax)}</td>
          </tr>
          <tr class="total-row">
            <td>Total:</td>
            <td class="amount">${formatCurrency(invoice.total)}</td>
          </tr>
        </table>

        <div class="footer">
          <div class="payment-info">
            <strong>Payment Information:</strong>
            <div>Bank: ${invoice.paymentInfo.bank}</div>
            <div>Account: ${invoice.paymentInfo.account}</div>
            <div>IBAN: ${invoice.paymentInfo.iban}</div>
          </div>
        </div>
      </div>
    </body>
    </html>
  `;
}

// Uso
const pdfBuffer = await generatePDF({
  html: generateInvoiceHTML(invoice),
});

// Guardar o enviar
await fs.writeFile(`invoice-${invoice.number}.pdf`, pdfBuffer);
```

---

## React-PDF

### Componente de Documento

```tsx
import {
  Document,
  Page,
  Text,
  View,
  StyleSheet,
  Image,
  Font,
} from '@react-pdf/renderer';

// Registrar fuentes
Font.register({
  family: 'Inter',
  fonts: [
    { src: '/fonts/Inter-Regular.ttf' },
    { src: '/fonts/Inter-Bold.ttf', fontWeight: 'bold' },
  ],
});

const styles = StyleSheet.create({
  page: {
    padding: 40,
    fontFamily: 'Inter',
    fontSize: 11,
  },
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginBottom: 40,
  },
  logo: {
    fontSize: 24,
    fontWeight: 'bold',
    color: '#2563eb',
  },
  table: {
    display: 'flex',
    width: '100%',
    marginTop: 20,
  },
  tableRow: {
    flexDirection: 'row',
    borderBottomWidth: 1,
    borderBottomColor: '#e5e7eb',
  },
  tableHeader: {
    backgroundColor: '#f3f4f6',
    fontWeight: 'bold',
  },
  tableCell: {
    padding: 8,
    flex: 1,
  },
  tableCellAmount: {
    padding: 8,
    flex: 1,
    textAlign: 'right',
  },
});

interface InvoiceProps {
  invoice: Invoice;
}

function InvoicePDF({ invoice }: InvoiceProps) {
  return (
    <Document>
      <Page size="A4" style={styles.page}>
        <View style={styles.header}>
          <Text style={styles.logo}>{invoice.company.name}</Text>
          <View>
            <Text>Invoice #{invoice.number}</Text>
            <Text>Date: {formatDate(invoice.date)}</Text>
          </View>
        </View>

        <View style={styles.table}>
          <View style={[styles.tableRow, styles.tableHeader]}>
            <Text style={styles.tableCell}>Description</Text>
            <Text style={styles.tableCell}>Qty</Text>
            <Text style={styles.tableCellAmount}>Price</Text>
            <Text style={styles.tableCellAmount}>Amount</Text>
          </View>

          {invoice.items.map((item, index) => (
            <View key={index} style={styles.tableRow}>
              <Text style={styles.tableCell}>{item.description}</Text>
              <Text style={styles.tableCell}>{item.quantity}</Text>
              <Text style={styles.tableCellAmount}>
                {formatCurrency(item.unitPrice)}
              </Text>
              <Text style={styles.tableCellAmount}>
                {formatCurrency(item.quantity * item.unitPrice)}
              </Text>
            </View>
          ))}
        </View>

        <View style={{ marginTop: 20, alignItems: 'flex-end' }}>
          <Text>Total: {formatCurrency(invoice.total)}</Text>
        </View>
      </Page>
    </Document>
  );
}

// Generar PDF
import { renderToBuffer } from '@react-pdf/renderer';

async function generateInvoice(invoice: Invoice): Promise<Buffer> {
  return renderToBuffer(<InvoicePDF invoice={invoice} />);
}
```

---

## PDFKit (Programático)

```typescript
import PDFDocument from 'pdfkit';

function generateReport(data: ReportData): Promise<Buffer> {
  return new Promise((resolve) => {
    const doc = new PDFDocument({ margin: 50 });
    const chunks: Buffer[] = [];

    doc.on('data', (chunk) => chunks.push(chunk));
    doc.on('end', () => resolve(Buffer.concat(chunks)));

    // Header
    doc.fontSize(20).text('Monthly Report', { align: 'center' });
    doc.moveDown();

    // Logo
    doc.image('logo.png', 50, 45, { width: 100 });

    // Content
    doc.fontSize(12).text(`Generated: ${new Date().toLocaleDateString()}`);
    doc.moveDown();

    // Table
    const tableTop = 150;
    const headers = ['Name', 'Quantity', 'Amount'];
    const columnWidths = [200, 100, 100];

    // Draw headers
    let x = 50;
    headers.forEach((header, i) => {
      doc.font('Helvetica-Bold').text(header, x, tableTop);
      x += columnWidths[i];
    });

    // Draw rows
    let y = tableTop + 25;
    data.items.forEach((item) => {
      x = 50;
      doc.font('Helvetica')
        .text(item.name, x, y)
        .text(item.quantity.toString(), x + columnWidths[0], y)
        .text(`$${item.amount.toFixed(2)}`, x + columnWidths[0] + columnWidths[1], y);
      y += 20;
    });

    // Footer
    doc.fontSize(10).text(
      'Page 1 of 1',
      50,
      doc.page.height - 50,
      { align: 'center' }
    );

    doc.end();
  });
}
```

---

## API Endpoint

```typescript
import { Router } from 'express';

const router = Router();

router.get('/invoices/:id/pdf', async (req, res) => {
  try {
    const invoice = await getInvoice(req.params.id);

    if (!invoice) {
      return res.status(404).json({ error: 'Invoice not found' });
    }

    const pdfBuffer = await generatePDF({
      html: generateInvoiceHTML(invoice),
    });

    res.set({
      'Content-Type': 'application/pdf',
      'Content-Disposition': `attachment; filename="invoice-${invoice.number}.pdf"`,
      'Content-Length': pdfBuffer.length,
    });

    res.send(pdfBuffer);
  } catch (error) {
    console.error('PDF generation failed:', error);
    res.status(500).json({ error: 'Failed to generate PDF' });
  }
});

// Streaming para PDFs grandes
router.get('/reports/:id/pdf', async (req, res) => {
  const report = await getReport(req.params.id);

  res.set({
    'Content-Type': 'application/pdf',
    'Content-Disposition': `inline; filename="report-${report.id}.pdf"`,
  });

  const stream = generateReportStream(report);
  stream.pipe(res);
});
```

---

## Referencias

- [Puppeteer PDF](https://pptr.dev/api/puppeteer.page.pdf)
- [React-PDF](https://react-pdf.org/)
- [PDFKit](http://pdfkit.org/)
- [jsPDF](https://github.com/parallax/jsPDF)

---

*Skill creada: 2026-02-01*
*Versión: 1.0.0*
