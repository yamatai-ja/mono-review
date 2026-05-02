import React from "react";
import { BsArrowRightCircle } from "react-icons/bs";
import { BiCalendarEdit, BiCategoryAlt } from "react-icons/bi";
import {
  IoLogoFacebook,
  IoLogoLinkedin,
  IoLogoPinterest,
  IoLogoTwitter,
  IoSearch,
} from "react-icons/io5";
import {
  FaAddressCard,
  FaEnvelope,
  FaHashtag,
  FaPhoneAlt,
} from "react-icons/fa";

// Re-export as proper React function components so Astro 6 can render them as React components.
export const BsArrowRightCircleIcon = (props: any) => <BsArrowRightCircle {...props} />;
export const BiCalendarEditIcon = (props: any) => <BiCalendarEdit {...props} />;
export const BiCategoryAltIcon = (props: any) => <BiCategoryAlt {...props} />;
export const IoLogoFacebookIcon = (props: any) => <IoLogoFacebook {...props} />;
export const IoLogoLinkedinIcon = (props: any) => <IoLogoLinkedin {...props} />;
export const IoLogoPinterestIcon = (props: any) => <IoLogoPinterest {...props} />;
export const IoLogoTwitterIcon = (props: any) => <IoLogoTwitter {...props} />;
export const IoSearchIcon = (props: any) => <IoSearch {...props} />;
export const FaAddressCardIcon = (props: any) => <FaAddressCard {...props} />;
export const FaEnvelopeIcon = (props: any) => <FaEnvelope {...props} />;
export const FaHashtagIcon = (props: any) => <FaHashtag {...props} />;
export const FaPhoneAltIcon = (props: any) => <FaPhoneAlt {...props} />;

// Also export under original names for compatibility
export {
  BsArrowRightCircle,
  BiCalendarEdit,
  BiCategoryAlt,
  IoLogoFacebook,
  IoLogoLinkedin,
  IoLogoPinterest,
  IoLogoTwitter,
  IoSearch,
  FaAddressCard,
  FaEnvelope,
  FaHashtag,
  FaPhoneAlt,
};
