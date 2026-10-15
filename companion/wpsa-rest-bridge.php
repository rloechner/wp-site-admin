<?php
/**
 * Plugin Name: WP Site Admin REST bridge (optional)
 * Description: Exposes Flamingo inbound messages to the REST API (read for users who can already read them in wp-admin) so the WP Site Admin bot can triage help requests. Drop into wp-content/mu-plugins/. Delete to revoke.
 * Version: 0.1.0
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
