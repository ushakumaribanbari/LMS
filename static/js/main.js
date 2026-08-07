(function () {
    const sidebar = document.getElementById('sidebar');
    const overlay = document.getElementById('sidebarOverlay');
    const toggle = document.getElementById('sidebarToggle');

    if (toggle && sidebar && overlay) {
        toggle.addEventListener('click', function () {
            sidebar.classList.toggle('open');
            overlay.classList.toggle('open');
        });
        overlay.addEventListener('click', function () {
            sidebar.classList.remove('open');
            overlay.classList.remove('open');
        });
    }

const searchInput = document.getElementById("pageSearch");

if (searchInput) {

    searchInput.addEventListener("input", async function () {

        const q = this.value.trim();

        if(q===""){

    document.getElementById("searchResults").innerHTML="";

    return;

}

        const res = await fetch("/search-courses?q="+encodeURIComponent(q));

        const data = await res.json();

        const resultBox = document.getElementById("searchResults");

if(!resultBox) return;

resultBox.innerHTML="";

        data.forEach(course => {

            resultBox.innerHTML += `
                <a href="/course/${course.id}" class="search-item">
                    ${course.title}
                </a>
            `;

        });

    });

}
})();
