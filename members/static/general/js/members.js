// Moved Olgas function into scripts file
const h = new Date().getHours();
document.getElementById("greeting").textContent = h < 12 ? "Good morning" : h < 18 ? "Good afternoon" : "Good evening";

