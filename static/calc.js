// Runs entirely in the browser using the price-break/MOQ data already
// embedded in the page - no extra server calls needed to recalculate.

function formatMoney(value) {
  if (value === null || value === undefined || isNaN(value)) return "\u2014";
  return value.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 4 });
}

function currentBreakFor(priceBreaks, qty) {
  // priceBreaks is sorted ascending by quantity. Pick the highest break
  // whose quantity is <= qty; if qty is below the first break, use the first.
  if (!priceBreaks.length) return null;
  let applicable = priceBreaks[0];
  for (const pb of priceBreaks) {
    if (pb.quantity <= qty) {
      applicable = pb;
    } else {
      break;
    }
  }
  return applicable;
}

function nextBreakAbove(priceBreaks, qty) {
  for (const pb of priceBreaks) {
    if (pb.quantity > qty) return pb;
  }
  return null;
}

function recalcRow(row) {
  const pricingRaw = row.dataset.pricing;
  const moqCell = row.querySelector(".moq-cell");
  const unitCell = row.querySelector(".unit-price-cell");
  const extCell = row.querySelector(".ext-cost-cell");
  const tipCell = row.querySelector(".tip-cell");
  const qtyInput = row.querySelector(".qty-input");

  if (!pricingRaw || pricingRaw === "null") {
    return;
  }

  const pricing = JSON.parse(pricingRaw);
  const priceBreaks = pricing.price_breaks || [];
  const minOrder = pricing.min_order || 1;
  const multiple = pricing.multiple || 1;

  moqCell.textContent = `MOQ ${minOrder}` + (multiple > 1 ? ` / x${multiple}` : "");

  let qty = parseInt(qtyInput.value, 10);
  if (!qty || qty < 1) qty = 1;

  if (!priceBreaks.length) {
    unitCell.textContent = "\u2014";
    extCell.textContent = "\u2014";
    tipCell.textContent = "No pricing data";
    return;
  }

  const current = currentBreakFor(priceBreaks, qty);
  const unitPrice = current.display_price;
  const totalCost = unitPrice * qty;

  unitCell.textContent = formatMoney(unitPrice);
  extCell.textContent = formatMoney(totalCost);

  // Build MOQ / multiple warnings and the "buy more to save" tip together.
  const notes = [];

  if (qty < minOrder) {
    notes.push(`Below MOQ of ${minOrder}`);
  }
  if (multiple > 1 && qty % multiple !== 0) {
    notes.push(`Not a multiple of ${multiple}`);
  }

  const next = nextBreakAbove(priceBreaks, qty);
  if (next) {
    const nextTotal = next.display_price * next.quantity;
    const extraUnits = next.quantity - qty;
    if (nextTotal < totalCost) {
      notes.push(
        `Buy ${extraUnits} more (total ${next.quantity}) for ${formatMoney(nextTotal)} instead of ${formatMoney(totalCost)}`
      );
    } else if (next.display_price < unitPrice) {
      notes.push(
        `${next.quantity}+ drops unit price to ${formatMoney(next.display_price)}, but costs ${formatMoney(nextTotal - totalCost)} more overall`
      );
    }
  }

  tipCell.textContent = notes.length ? notes.join(" \u2022 ") : "\u2014";
  tipCell.classList.toggle("warning-tip", notes.some(n => n.startsWith("Below") || n.startsWith("Not a multiple")));
}

function init() {
  document.querySelectorAll(".calc-row").forEach((row) => {
    recalcRow(row);
    const qtyInput = row.querySelector(".qty-input");
    qtyInput.addEventListener("input", () => recalcRow(row));
  });
}

document.addEventListener("DOMContentLoaded", init);
