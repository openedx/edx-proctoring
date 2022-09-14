/**
 * Declarations of global variables that are created implicitly in files under test
 *
 * This is a kludge to workaround PhantomJS disliking implicit global
 * creation without a `var` declaration, which we rely on for the
 * order-agnostic global setting pattern we always do to namespace
 * global variables.
 */
// eslint-disable-next-line no-unused-vars
var edx;
