$(document).ready(function () {
    $(document).on('click', '[data-tree-toggle]', function () {
        const targetId = $(this).data('tree-toggle');
        const $target = $(`#${targetId}`);
        if (!$target.length) return;

        const expanded = !$(this).hasClass('is-open');
        $(this).toggleClass('is-open', expanded);
        $(this).attr('aria-expanded', expanded ? 'true' : 'false');
        $target.toggleClass('d-none', !expanded);
    });
});
