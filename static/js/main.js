document.addEventListener('DOMContentLoaded', function () {
    var menuButton = document.getElementById('homeMenuButton');
    var mobileMenu = document.getElementById('homeMobileMenu');

    if (!menuButton || !mobileMenu) {
        return;
    }

    function closeMenu() {
        mobileMenu.classList.remove('is-open');
        menuButton.setAttribute('aria-expanded', 'false');
        menuButton.setAttribute('aria-label', '메뉴 열기');
    }

    function openMenu() {
        mobileMenu.classList.add('is-open');
        menuButton.setAttribute('aria-expanded', 'true');
        menuButton.setAttribute('aria-label', '메뉴 닫기');
    }

    function toggleMenu() {
        var isOpen = mobileMenu.classList.contains('is-open');
        if (isOpen) {
            closeMenu();
        } else {
            openMenu();
        }
    }

    menuButton.addEventListener('click', function (e) {
        e.stopPropagation();
        toggleMenu();
    });

    // 모바일 메뉴 링크 클릭 시 자동으로 닫기
    var mobileLinks = mobileMenu.querySelectorAll('.home-mobile-link');
    mobileLinks.forEach(function (link) {
        link.addEventListener('click', closeMenu);
    });

    // 메뉴 바깥 클릭 시 닫기
    document.addEventListener('click', function (e) {
        if (mobileMenu.classList.contains('is-open') &&
            !mobileMenu.contains(e.target) &&
            !menuButton.contains(e.target)) {
            closeMenu();
        }
    });

    // 화면 크기가 커지면 모바일 메뉴 상태 초기화
    window.addEventListener('resize', function () {
        if (window.innerWidth > 860) {
            closeMenu();
        }
    });

    // ESC 키로 닫기
    document.addEventListener('keydown', function (e) {
        if (e.key === 'Escape') {
            closeMenu();
        }
    });
});