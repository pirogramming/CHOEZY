document.addEventListener("DOMContentLoaded", () => {
  const donut = document.querySelector(".report-donut[data-other-start]");
  const tooltip = donut?.querySelector(".report-donut-tooltip");
  const otherLegend = document.querySelector(".report-legend__other");

  if (!donut || !tooltip) return;

  const startAngle = Number(donut.dataset.otherStart) * 3.6;
  const endAngle = Number(donut.dataset.otherEnd) * 3.6;
  let pinned = false;

  const showTooltip = (x, y) => {
    tooltip.style.left = `${x}px`;
    tooltip.style.top = `${y}px`;
    tooltip.hidden = false;
  };

  const hideTooltip = () => {
    if (!pinned) tooltip.hidden = true;
  };

  const pointIsInOtherSlice = (event) => {
    const rect = donut.getBoundingClientRect();
    const x = event.clientX - rect.left;
    const y = event.clientY - rect.top;
    const dx = x - rect.width / 2;
    const dy = y - rect.height / 2;
    const radius = Math.hypot(dx, dy);
    const innerRadius = rect.width * (90 / 280);
    const outerRadius = rect.width / 2;
    const angle = (Math.atan2(dy, dx) * 180 / Math.PI + 450) % 360;

    return {
      matches:
        radius >= innerRadius &&
        radius <= outerRadius &&
        angle >= startAngle &&
        angle <= endAngle,
      x,
      y,
    };
  };

  donut.addEventListener("pointermove", (event) => {
    if (pinned) return;

    const point = pointIsInOtherSlice(event);
    if (point.matches) {
      showTooltip(point.x + 12, point.y + 12);
    } else {
      tooltip.hidden = true;
    }
  });

  donut.addEventListener("pointerleave", hideTooltip);

  donut.addEventListener("click", (event) => {
    const point = pointIsInOtherSlice(event);
    if (!point.matches) {
      pinned = false;
      tooltip.hidden = true;
      return;
    }

    pinned = !pinned;
    if (pinned) showTooltip(point.x + 12, point.y + 12);
    else tooltip.hidden = true;
  });

  if (otherLegend) {
    const showFromLegend = () => {
      showTooltip(donut.clientWidth / 2 + 20, donut.clientHeight / 2);
    };

    otherLegend.addEventListener("pointerenter", showFromLegend);
    otherLegend.addEventListener("pointerleave", hideTooltip);
    otherLegend.addEventListener("focus", showFromLegend);
    otherLegend.addEventListener("blur", hideTooltip);
    otherLegend.addEventListener("click", () => {
      pinned = !pinned;
      if (pinned) showFromLegend();
      else tooltip.hidden = true;
    });
  }
});
