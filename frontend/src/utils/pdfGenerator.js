import { jsPDF } from "jspdf";
import autoTable from "jspdf-autotable";

export const generatePurchaseOrderPDF = (result) => {
  const doc = new jsPDF();

  // Header Section
  doc.setFont("helvetica", "bold");
  doc.setFontSize(22);
  doc.text("PURCHASE ORDER", 14, 22);

  doc.setFont("helvetica", "normal");
  doc.setFontSize(10);
  doc.text(`Date: ${new Date().toLocaleDateString()}`, 14, 30);
  doc.text(`PO Number: ${result.po_number || "N/A"}`, 14, 36);

  // Supplier & Delivery Info
  doc.setFont("helvetica", "bold");
  doc.setFontSize(12);
  doc.text("Supplier Details", 14, 46);
  
  doc.setFont("helvetica", "normal");
  doc.setFontSize(10);
  doc.text(`Name: ${result.supplier_name || "N/A"}`, 14, 52);
  doc.text(`Expected Delivery: ${result.expected_delivery_date || "N/A"}`, 14, 58);

  // Order Items Table
  const tableData = [
    [
      "1", 
      `Equipment/Service: ${result.item || "Requested Procurement"}`, 
      result.quantity || "1", 
      `${result.subtotal?.toFixed(2) || "0.00"} ${result.currency || "USD"}`
    ]
  ];

  autoTable(doc, {
    startY: 68,
    head: [["#", "Description", "Quantity", "Total Amount"]],
    body: tableData,
    theme: "striped",
    headStyles: { fillColor: [59, 130, 246] }, // Tailwind blue-500
    styles: { font: "helvetica", fontSize: 10 },
  });

  // Footer Totals
  const finalY = doc.lastAutoTable.finalY + 10;
  
  doc.setFont("helvetica", "bold");
  doc.setFontSize(12);
  doc.text("Final Calculation", 14, finalY);

  doc.setFont("helvetica", "normal");
  doc.setFontSize(10);
  doc.text(`Subtotal: ${result.subtotal?.toFixed(2) || "0.00"} ${result.currency || "USD"}`, 14, finalY + 8);
  doc.setFont("helvetica", "bold");
  doc.text(`Total Due: ${result.total?.toFixed(2) || "0.00"} ${result.currency || "USD"}`, 14, finalY + 14);

  // Formal Notice or Notes
  if (result.formal_notice) {
    doc.setFont("helvetica", "italic");
    doc.setFontSize(9);
    doc.setTextColor(100);
    const splitNotice = doc.splitTextToSize(`Notes: ${result.formal_notice}`, 180);
    doc.text(splitNotice, 14, finalY + 28);
  }

  // Action
  doc.save(`${result.po_number || "purchase_order"}.pdf`);
};
