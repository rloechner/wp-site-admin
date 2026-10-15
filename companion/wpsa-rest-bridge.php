<?php
/**
 * Plugin Name: WP Site Admin REST bridge (optional)
 * Description: Exposes Flamingo inbound messages to the REST API (read for users who can already read them in wp-admin) so the WP Site Admin bot can triage help requests, plus admin-only update endpoints (list updates; update one plugin, theme, or core) using WordPress's own upgraders. Drop into wp-content/mu-plugins/. Delete to revoke.
 * Version: 0.3.0
 */
add_filter( 'register_post_type_args', function ( $args, $type ) {
	if ( 'flamingo_inbound' === $type ) {
		$args['show_in_rest'] = true;
		$args['rest_base']    = 'flamingo_inbound';
	}
	return $args;
}, 10, 2 );

add_action( 'rest_api_init', function () {
	register_rest_field( 'flamingo_inbound', 'wpsa', array(
		'get_callback' => function ( $post ) {
			if ( ! current_user_can( 'flamingo_edit_inbound_message', $post['id'] ) ) return null;
			$fields = array();
			foreach ( (array) get_post_meta( $post['id'], '_field', false ) as $k ) {}
			foreach ( get_post_meta( $post['id'] ) as $key => $val ) {
				if ( 0 === strpos( $key, '_field_' ) ) $fields[ substr( $key, 7 ) ] = maybe_unserialize( $val[0] );
			}
			return array(
				'subject'    => get_post_meta( $post['id'], '_subject', true ),
				'from_name'  => get_post_meta( $post['id'], '_from_name', true ),
				'from_email' => get_post_meta( $post['id'], '_from_email', true ),
				'fields'     => $fields,
				'spam'       => 'flamingo-spam' === get_post_status( $post['id'] ),
				'channel'    => wp_get_post_terms( $post['id'], 'flamingo_inbound_channel', array( 'fields' => 'slugs' ) ),
			);
		},
	) );
} );

/*
 * Updates (v0.3.0): admin-only endpoints that run WordPress's own upgraders.
 * Auth: any WordPress REST auth (Application Password for the bot; cookie + X-WP-Nonce for browsers).
 * Each endpoint checks the matching capability (update_plugins / update_themes / update_core),
 * so it can never do more than the authenticated user could do in wp-admin.
 * Respects DISALLOW_FILE_MODS. Updates exactly one item per request; no auto-updates.
 */
add_action( 'rest_api_init', function () {
	$ns = 'wpsa/v1';
	register_rest_route( $ns, '/updates', array(
		'methods'             => 'GET',
		'permission_callback' => function () { return current_user_can( 'update_plugins' ) || current_user_can( 'update_themes' ) || current_user_can( 'update_core' ); },
		'callback'            => 'wpsa_list_updates',
	) );
	register_rest_route( $ns, '/update/plugin', array(
		'methods'             => 'POST',
		'permission_callback' => function () { return current_user_can( 'update_plugins' ); },
		'args'                => array( 'plugin' => array( 'required' => true, 'type' => 'string' ) ),
		'callback'            => 'wpsa_update_plugin',
	) );
	register_rest_route( $ns, '/update/theme', array(
		'methods'             => 'POST',
		'permission_callback' => function () { return current_user_can( 'update_themes' ); },
		'args'                => array( 'theme' => array( 'required' => true, 'type' => 'string' ) ),
		'callback'            => 'wpsa_update_theme',
	) );
	register_rest_route( $ns, '/update/core', array(
		'methods'             => 'POST',
		'permission_callback' => function () { return current_user_can( 'update_core' ); },
		'callback'            => 'wpsa_update_core',
	) );
} );

function wpsa_upgrader_includes() {
	require_once ABSPATH . 'wp-admin/includes/file.php';
	require_once ABSPATH . 'wp-admin/includes/plugin.php';
	require_once ABSPATH . 'wp-admin/includes/misc.php';
	require_once ABSPATH . 'wp-admin/includes/update.php';
	require_once ABSPATH . 'wp-admin/includes/theme.php';
	require_once ABSPATH . 'wp-admin/includes/class-wp-upgrader.php';
}

function wpsa_file_mods_blocked() {
	if ( defined( 'DISALLOW_FILE_MODS' ) && DISALLOW_FILE_MODS ) {
		return new WP_Error( 'wpsa_file_mods_disallowed', 'DISALLOW_FILE_MODS is set; updates must be done by the host or over SSH.', array( 'status' => 409 ) );
	}
	if ( 'direct' !== get_filesystem_method() ) {
		return new WP_Error( 'wpsa_fs_not_direct', 'WordPress needs FTP credentials to write files on this host; use WP-CLI/SSH or wp-admin instead.', array( 'status' => 409 ) );
	}
	return false;
}

function wpsa_list_updates() {
	wpsa_upgrader_includes();
	wp_update_plugins(); wp_update_themes(); wp_version_check( array(), true );
	$out = array( 'plugins' => array(), 'themes' => array(), 'core' => null, 'file_mods_allowed' => ! wpsa_file_mods_blocked() );
	foreach ( get_plugin_updates() as $file => $p ) {
		$out['plugins'][] = array( 'plugin' => $file, 'name' => $p->Name, 'installed' => $p->Version, 'new_version' => $p->update->new_version, 'active' => is_plugin_active( $file ), 'tested' => $p->update->tested ?? null, 'requires_php' => $p->update->requires_php ?? null );
	}
	foreach ( get_theme_updates() as $slug => $t ) {
		$out['themes'][] = array( 'theme' => $slug, 'name' => $t->get( 'Name' ), 'installed' => $t->get( 'Version' ), 'new_version' => $t->update['new_version'], 'active' => get_stylesheet() === $slug );
	}
	$core = get_preferred_from_update_core();
	if ( $core && 'upgrade' === $core->response ) $out['core'] = array( 'installed' => get_bloginfo( 'version' ), 'new_version' => $core->current );
	return $out;
}

function wpsa_update_plugin( WP_REST_Request $req ) {
	wpsa_upgrader_includes();
	if ( $e = wpsa_file_mods_blocked() ) return $e;
	$file = $req['plugin'];
	$all  = get_plugins();
	if ( ! isset( $all[ $file ] ) ) return new WP_Error( 'wpsa_no_plugin', "Plugin $file not installed.", array( 'status' => 404 ) );
	$before = $all[ $file ]['Version'];
	$was_active = is_plugin_active( $file );
	wp_update_plugins();
	$skin = new WP_Ajax_Upgrader_Skin();
	$result = ( new Plugin_Upgrader( $skin ) )->upgrade( $file );
	wp_clean_plugins_cache();
	$after = get_plugins()[ $file ]['Version'] ?? null;
	if ( $was_active && ! is_plugin_active( $file ) ) activate_plugin( $file, '', false, true );
	return array( 'plugin' => $file, 'before' => $before, 'after' => $after, 'ok' => ( true === $result || is_array( $result ) ) && $after !== $before,
		'active' => is_plugin_active( $file ), 'result' => is_wp_error( $result ) ? $result->get_error_message() : $result, 'messages' => $skin->get_upgrade_messages(),
		'errors' => $skin->get_errors()->get_error_messages() );
}

function wpsa_update_theme( WP_REST_Request $req ) {
	wpsa_upgrader_includes();
	if ( $e = wpsa_file_mods_blocked() ) return $e;
	$slug = $req['theme'];
	$t = wp_get_theme( $slug );
	if ( ! $t->exists() ) return new WP_Error( 'wpsa_no_theme', "Theme $slug not installed.", array( 'status' => 404 ) );
	$before = $t->get( 'Version' );
	wp_update_themes();
	$skin = new WP_Ajax_Upgrader_Skin();
	$result = ( new Theme_Upgrader( $skin ) )->upgrade( $slug );
	wp_clean_themes_cache();
	$after = wp_get_theme( $slug )->get( 'Version' );
	return array( 'theme' => $slug, 'before' => $before, 'after' => $after, 'ok' => $after !== $before, 'result' => is_wp_error( $result ) ? $result->get_error_message() : $result,
		'messages' => $skin->get_upgrade_messages(), 'errors' => $skin->get_errors()->get_error_messages() );
}

function wpsa_update_core() {
	wpsa_upgrader_includes();
	if ( $e = wpsa_file_mods_blocked() ) return $e;
	wp_version_check( array(), true );
	$offer = get_preferred_from_update_core();
	$before = get_bloginfo( 'version' );
	if ( ! $offer || 'upgrade' !== $offer->response ) return array( 'ok' => true, 'before' => $before, 'after' => $before, 'note' => 'Already up to date.' );
	$skin = new WP_Ajax_Upgrader_Skin();
	$result = ( new Core_Upgrader( $skin ) )->upgrade( $offer );
	return array( 'before' => $before, 'after' => is_wp_error( $result ) ? $before : $result, 'ok' => ! is_wp_error( $result ),
		'result' => is_wp_error( $result ) ? $result->get_error_message() : $result, 'messages' => $skin->get_upgrade_messages() );
}
